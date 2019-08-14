"""
PaStA - Patch Stack Analysis

Copyright (c) BMW Cat It, 2019

Author:
  Sebastian Duda <sebastian.duda@fau.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import email
import os
import pickle
import re

from anytree import LevelOrderIter
from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.LinuxMailCharacteristics import LinuxMailCharacteristics, \
    load_linux_mail_characteristics

log = getLogger(__name__[-15:])

_repo = None
_config = None
_p = None

d_resources = './resources/linux/resources/'

MAINLINE_REGEX = re.compile(r'^v(\d+\.\d+|2\.6\.\d+)(-rc\d+)?$')


def write_cell(file, string):
    string = str(string).replace('\'', '`').replace('"', '`').replace('\n', '|').replace('\t', ' ').replace('=', '-')
    file.write(string + '\t')


def write_dict_list(_list, name):
    f = open(name, 'w')
    for k in _list[0].keys():
        write_cell(f, k)
    f.write('\n')
    for data in _list:
        for k in data.keys():
            write_cell(f, data[k])
        f.write('\n')


def get_pool():
    global _p
    if _p is None:
        _p = Pool(processes=cpu_count(), maxtasksperchild=10)
    return _p


def is_part_of_patch_set(patch):
    try:
        return re.search(r'[0-9]+/[0-9]+\]', _repo[patch].mail_subject) is not None
    except KeyError:
        return False


def get_patch_set(patch):
    result = set()
    result.add(patch)
    thread = threads.get_thread(patch)

    if thread.children is None:
        return result

    if not is_part_of_patch_set(patch):
        return result

    cover = thread  # this only works if
    result.add(cover.name)

    # get leaves of cover letter
    for child in cover.children:
        result.add(child.name)
    return result


def get_author_of_msg(repo, msg_id):
    email = repo.mbox.get_messages(msg_id)[0]
    return email['From'].lower()


def patch_has_foreign_response(repo, patch):
    thread = repo.mbox.threads.get_thread(patch)

    if len(thread.children) == 0:
        return False  # If there is no response the check is trivial

    author = get_author_of_msg(repo, patch)

    for mail in list(LevelOrderIter(thread)):
        # Beware, the mail might be virtual
        if mail.name not in repo:
            continue

        this_author = get_author_of_msg(repo, mail.name)
        if this_author != author:
            return True
    return False


def is_single_patch_ignored(patch):
    return patch, not patch_has_foreign_response(_repo, patch)


def get_authors_in_thread(repo, thread):
    authors = set()

    authors.add(get_author_of_msg(repo, thread.name))

    for child in thread.children:
        authors |= get_authors_in_thread(repo, child)

    return authors


def get_ignored(repo, mail_characteristics, clustering):
    # First, we have to define the term patch. In this analysis, we must only
    # regard patches that either fulfil rule 1 or 2:
    #
    # 1. Patch is the parent of a thread.
    #    This covers classic one-email patches
    #
    # 2. Patch is the 1st level child of the parent of a thread
    #    In this case, the parent can either be a patch (e.g., a series w/o
    #    cover letter) or not a patch (e.g., parent is a cover letter)
    #
    # 3. The patch must not be sent from a bot (e.g., tip-bot)
    #
    # 4. Ignore stable review patches
    #
    # All other patches MUST be ignored. Rationale: Maintainers may re-send
    # the patch as a reply of the discussion. Such patches must be ignored.
    # Example: Look at the thread of
    #     <20190408072929.952A1441D3B@finisterre.ee.mobilebroadband>

    population_all_patches = set()
    population_not_accepted = set()
    population_accepted = set()
    not_upstreamed_patches = set()
    upstreamed_patches = set()

    skipped_bot = 0
    skipped_stable = 0
    skipped_not_linux = 0
    skipped_not_first_patch = 0

    for downstream, upstream in clustering.iter_split():
        # Dive into downstream, and check the above-mentioned criteria
        relevant = set()
        for d in downstream:
            skip = False
            population_all_patches.add(d)

            if len(upstream):
                population_accepted.add(d)
            else:
                population_not_accepted.add(d)

            characteristics = mail_characteristics[d]
            if characteristics.is_from_bot:
                skipped_bot += 1
                skip = True
            if characteristics.is_stable_review:
                skipped_stable += 1
                skip = True
            if not characteristics.patches_linux:
                skipped_not_linux += 1
                skip = True
            if not characteristics.is_first_patch_in_thread:
                skipped_not_first_patch += 1
                skip = True

            if skip:
                continue

            relevant.add(d)

        # Nothing left? Skip the cluster.
        if len(relevant) == 0:
            continue

        if len(upstream):
            upstreamed_patches |= relevant
        else:
            not_upstreamed_patches |= relevant

    # For all patches of the population, check if they were ignored
    global _repo
    _repo = repo

    p = Pool(cpu_count())
    population_ignored = dict(p.map(is_single_patch_ignored, tqdm(population_all_patches)))
    p.close()
    p.join()
    _repo = None

    population_relevant = upstreamed_patches | not_upstreamed_patches

    # Calculate ignored patches
    ignored_patches = {patch for (patch, is_ignored) in population_ignored.items()
                       if patch in not_upstreamed_patches and
                          is_ignored == True}

    # Calculate ignored patches wrt to other patches in the cluster: A patch is
    # considered as ignored, if all related patches were ignoreed as well
    ignored_patches_related = {patch for (patch, is_ignored) in
            population_ignored.items()
                               if patch in not_upstreamed_patches and
                                  False not in [population_ignored[x] for x in clustering.get_downstream(patch)]}

    # Create a dictionary list-name -> number of overall patches. We can use it
    # to calculate a per-list fraction of ignored patches
    num_patches_on_list = dict()
    for patch in population_relevant:
        lists = repo.mbox.get_lists(patch)
        for mlist in lists:
            if mlist not in num_patches_on_list:
                num_patches_on_list[mlist] = 0
            num_patches_on_list[mlist] += 1

    num_ignored_patches = len(ignored_patches)
    num_ignored_patches_related = len(ignored_patches_related)

    num_population_accepted = len(population_accepted)
    num_population_not_accepted = len(population_not_accepted)
    num_population_relevant = len(population_relevant)

    log.info('All patches: %u' % len(population_all_patches))
    log.info('Skipped patches:')
    log.info('  Bot: %u' % skipped_bot)
    log.info('  Stable: %u' % skipped_stable)
    log.info('  Not Linux: %u' % skipped_not_linux)
    log.info('  Not first patch in series: %u' % skipped_not_first_patch)
    log.info('Not accepted patches: %u' % num_population_not_accepted)
    log.info('Accepted patches: %u' % num_population_accepted)
    log.info('Num relevant patches: %u' % num_population_relevant)
    log.info('Found %u ignored patches' % num_ignored_patches)
    log.info('Fraction of ignored patches: %0.3f' %
             (num_ignored_patches / num_population_relevant))
    log.info('Found %u ignored patches (related)' % num_ignored_patches_related)
    log.info('Fraction of ignored related patches: %0.3f' %
            (num_ignored_patches_related / num_population_relevant))

    hs_ignored  = count_lists(repo, ignored_patches, 'Highscore lists / ignored patches')
    hs_ignored_rel = count_lists(repo, ignored_patches_related,
                                 'Highscore lists / ignored patches (related)')

    def highscore_fraction(highscore, description):
        result = dict()
        for mlist, count in highscore.items():
            result[mlist] = count / num_patches_on_list[mlist]

        print(description)
        for mlist, fraction in sorted(result.items(), key = lambda x: x[1]):
            print('  List %s: %0.3f' % (mlist, fraction))

    highscore_fraction(hs_ignored, 'Highscore fraction ignored patches')
    highscore_fraction(hs_ignored_rel,
                       'Highscore fraction ignored patches (related)')

    dump_messages(os.path.join(d_resources, 'ignored_patches'), repo,
                  ignored_patches)
    dump_messages(os.path.join(d_resources, 'ignored_patches_related'), repo,
                  ignored_patches_related)
    dump_messages(os.path.join(d_resources, 'base'), repo, population_relevant)


def get_recipients(message):
    recipients = message.get_all('To') + message.get_all('Cc')
    recipients = {x[1] for x in email.utils.getaddresses(recipients)}

    return recipients


def check_wrong_maintainer_patch(repo, maintainer, message_id):
    message = repo.mbox.get_messages(message_id)[0]
    patch = repo[message_id]

    recipients = get_recipients(message)
    subsystems = maintainer.get_subsystems_by_files(patch.diff.affected)

    subsystem = subsystems[patch]
    if subsystem is None:
        return None, None

    some = False
    all = True

    for maintainer in subsystem['maintainers']:
        if maintainer in recipients_clean:
            some = True

    for maintainer in subsystem['maintainers'] | subsystem['supporter'] | subsystem['odd fixer'] | subsystem['reviewer']:
        if maintainer not in recipients_clean:
            all = False

    if all:
        return None, None
    if some:
        return None, patch
    return patch, None


def patch_get_version(patches_by_version, patch):
    for version, patches in patches_by_version.items():
        if patch in patches:
            return version
    return None


def check_wrong_maintainer(repo, maintainers_version, patches_by_version,
                           patches):
    #global _repo
    #_repo = repo
    #p = get_pool()
    ##return_value = p.map(_check_wrong_maintainer_patch, tqdm(patches))
    #return_value = list(map(_check_wrong_maintainer_patch, tqdm(patches)))
    #p.close()
    #p.join()
    #_repo = None

    for patch in patches:
        version = patch_get_version(patches_by_version, patch)
        maintainer = maintainers_version[version]
        result = check_wrong_maintainer_patch(repo, maintainer, patch)



    min = set()
    max = set()

    for res in return_value:
        min.add(res[0])
        max.add(res[1])

    try:
        min.remove(None)
    except KeyError:
        pass

    try:
        max.remove(None)
    except KeyError:
        pass

    pickle.dump((min, max), open('resources/linux/check_maintainer.pkl', 'wb'))
    return min, max


def is_patch_process_mail(patch):
    try:
        patch_mail = _repo.mbox[patch]
    except KeyError:
        return None
    subject = patch_mail.mail_subject.lower()
    if 'linux-next' in subject:
        return patch
    if 'git pull' in subject:
        return patch
    if 'rfc' in subject:
        return patch
    return None


def identify_process_mails():
    global patches
    p = get_pool()
    result = p.map(is_patch_process_mail, tqdm(patches))

    if result is None:
        return None
    result = set(result)
    try:
        result.remove(None)
    except KeyError:
        pass

    pickle.dump(result, open('resources/linux/process_mails.pkl', 'wb'))
    return result


def evaluate_patch(patch):

    global tags
    global patches_by_version
    global subsystems
    global ignored_patches
    global wrong_maintainer
    global process_mails
    global threads
    global upstream

    email = _repo.mbox.get_messages(patch)[0]
    author = email['From'].replace('\'', '"')
    thread = threads.get_thread(patch)
    mail_traffic = sum(1 for _ in LevelOrderIter(thread))
    first_mail_in_thread = thread.name
    patchobj = _repo[patch]

    to = email['To'] if email['To'] else ''
    cc = email['Cc'] if email['Cc'] else ''

    recipients = to + cc

    for k in patches_by_version.keys():
        if patch in patches_by_version[k]:
            tag = k
    rc = 'rc' in tag

    if rc:
        rcv = re.search('-rc[0-9]+', tag).group()[3:]
        version = re.search('v[0-9]+\.', tag).group() + '%02d' % int(re.search('\.[0-9]+', tag).group()[1:])
    else:
        rcv = 0
        version = re.search('v[0-9]+\.', tag).group() + '%02d' % (
                int(re.search('\.[0-9]+', tag).group()[1:]) + 1)

    subsystem = subsystems[patch]

    return {
        'id': patch,
        'subject': email['Subject'],
        'from': author,
        'ignored': patch in ignored_patches if ignored_patches else None,
        'upstream': patch in upstream,
        'wrong maintainer': patch in wrong_maintainer[0] if wrong_maintainer else None,
        'semi wrong maintainer': patch in wrong_maintainer[1] if wrong_maintainer else None,
        '#LoC': patchobj.diff.lines,
        '#Files': len(patchobj.diff.affected),
        '#recipients without lists': len(re.findall('<', recipients)),
        '#recipients': len(re.findall('@', recipients)),
        'timestamp': patchobj.author.date.timestamp(),
        'after version': tag,
        'rcv': rcv,
        'kernel version': version,
        'maintainers': subsystem['maintainers'] if subsystem else None,
        'helping': (subsystem['supporter'] | subsystem['odd fixer'] | subsystem['reviewer']) if subsystem else None,
        'lists': subsystem['lists'] if subsystem else None,
        'subsystems': subsystem['subsystem'] if subsystem else None,
        'mailTraffic': mail_traffic,
        'firstMailInThread': first_mail_in_thread,
        'process_mail': patch in process_mails if process_mails else None,
    }


def _evaluate_patches():
    p = get_pool()
    result = p.map(evaluate_patch, tqdm(patches))

    return result


def load_maintainers(tag):
    pyrepo = _repo.repo

    tag_hash = pyrepo.lookup_reference('refs/tags/%s' % tag).target
    commit_hash = pyrepo[tag_hash].target
    maintainers_blob_hash = pyrepo[commit_hash].tree['MAINTAINERS'].id
    maintainers = pyrepo[maintainers_blob_hash].data

    try:
        maintainers = maintainers.decode('utf-8')
    except:
        # older versions use ISO8859
        maintainers = maintainers.decode('iso8859')

    m = LinuxMaintainers(maintainers)

    return tag, m


def load_pkl_or_execute(filename, command):
    if os.path.isfile(filename):
        return pickle.load(open(filename, 'rb'))

    ret = command()
    pickle.dump(ret, open(filename, 'wb'))

    return ret


def count_lists(repo, patches, description, minimum=50):
    log.info(description)
    # Get the lists where those patches come from
    patch_origin_count = dict()
    for patch in patches:
        lists = repo.mbox.get_lists(patch)

        for list in lists:
            if list not in patch_origin_count:
                patch_origin_count[list] = 0
            patch_origin_count[list] += 1

    for listname, count in sorted(patch_origin_count.items(),
                                  key=lambda x: x[1]):
        if count < minimum:
            continue

        log.info('  List: %s\t\t%u' % (listname, count))

    return patch_origin_count


def get_patch_origin(repo, characteristics, messages):
    # Some primitive statistics. Where do non-linux patches come from?
    linux_patches = set()
    non_linux_patches = set()

    for patch in messages - repo.mbox.invalid:
        characteristic = characteristics[patch]
        if characteristic.patches_linux:
            linux_patches.add(patch)
        else:
            non_linux_patches.add(patch)

    log.info('%0.3f%% of all patches patch Linux' %
             (len(linux_patches) / (len(linux_patches) + len(non_linux_patches))))

    count_lists(repo, linux_patches, 'High freq lists of Linux-only patches')
    count_lists(repo, non_linux_patches, 'High freq lists of non-Linux patches')
    count_lists(repo, messages, 'High freq lists (all emails)')


def dump_messages(filename, repo, messages):
    with open(filename, 'w') as f:
        for message in sorted(messages):
            f.write('%s\t\t\t%s\n' % (message , ' '.join(sorted(repo.mbox.get_lists(message)))))


def evaluate_patches(config, prog, argv):
    if config.mode != config.Mode.MBOX:
        log.error('Only works in Mbox mode!')
        return -1

    repo = config.repo
    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()
    repo.mbox.load_threads()

    patches = set()
    upstream = set()
    for d, u in clustering.iter_split():
        patches |= d
        upstream |= u

    all_messages_in_time_window = repo.mbox.message_ids(config.mbox_time_window,
                                                        allow_invalid=True)
    characteristics = load_linux_mail_characteristics(repo,
                                                      all_messages_in_time_window)

    get_patch_origin(repo, characteristics, all_messages_in_time_window)


    log.info('Assigning patches to tags...')
    # Only respect mainline versions. No stable versions like v4.2.3
    mainline_tags = list(filter(lambda x: MAINLINE_REGEX.match(x[0]), repo.tags))
    patches_by_version = dict()
    for patch in patches:
        author_date = repo[patch].author.date
        tag = None
        for cand_tag, cand_tag_date in mainline_tags:
            if cand_tag_date > author_date:
                break
            tag = cand_tag

        if tag is None:
            log.error('No tag found for patch %s' % patch)
            quit(-1)

        if tag not in patches_by_version:
            patches_by_version[tag] = set()

        patches_by_version[tag].add(patch)

    log.info('Loading relevant MAINTAINERS files...')

    def load_all_maintainers():
        ret = dict()

        tags = {x[0] for x in repo.tags if not x[0].startswith('v2.6')}
        # WORKAROUND:
        tags = set(patches_by_version.keys())

        global _repo
        _repo = repo
        p = Pool(processes=cpu_count())
        for tag, maintainers in tqdm(p.imap_unordered(load_maintainers, tags),
                                     total=len(tags), desc='MAINTAINERS'):
            ret[tag] = maintainers
        p.close()
        p.join()
        _repo = None
        return ret

    maintainers_version = load_pkl_or_execute(os.path.join(d_resources, 'maintainers.pkl'),
                                              load_all_maintainers)

    #log.info('Assigning subsystems to patches...')
    #for tag, patches in patches_by_version.items():
    #    maintainers = maintainers_version[tag]
    #    for patch in patches:
    #        files = repo[patch].diff.affected
    #        subsystems = maintainers.get_subsystems_by_files(files)
    #        continue

    #log.info('Identify ignored patches...')
    #get_ignored(repo, characteristics, clustering)

    check_wrong_maintainer(repo, maintainers_version, patches_by_version,
                           patches)
    quit()

    log.info('Identify patches sent to wrong maintainers…')  # ####################################### Wrong Maintainer
    if 'no-check-maintainer' in argv:
        wrong_maintainer = None
    elif 'check-maintainer' in argv or not os.path.isfile('resources/linux/check_maintainer.pkl'):
        wrong_maintainer = check_wrong_maintainer()
    else:
        wrong_maintainer = pickle.load(open('resources/linux/check_maintainer.pkl', 'rb'))

    log.info('Identify process patches (eg. git pull)…')  # ############################################# Process Mails
    if 'no-process-mails' in argv:
        process_mails = None
    elif 'process-mails' in argv or not os.path.isfile('resources/linux/process_mails.pkl'):
        process_mails = identify_process_mails()
    else:
        process_mails = pickle.load(open('resources/linux/process_mails.pkl', 'rb'))

    result = _evaluate_patches()

    write_dict_list(result, 'patch_evaluation.tsv')
    pickle.dump(result, open('patch_evaluation.pkl', 'wb'))

    log.info("Clean up…")
    p = get_pool()
    p.close()
    p.join()

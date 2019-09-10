"""
PaStA - Patch Stack Analysis

Copyright (c) BMW Cat It, 2019

Author:
  Sebastian Duda <sebastian.duda@fau.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import os
import pickle
import re

from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.LinuxMailCharacteristics import load_linux_mail_characteristics

log = getLogger(__name__[-15:])

_repo = None
_config = None
_p = None

d_resources = './resources/linux/resources/'
f_prefix = 'eval_'
f_suffix = '.pkl'

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')


def f_pkl(fname):
    return '%s%s%s%s' % (d_resources, f_prefix, fname, f_suffix)


def get_ignored(repo, characteristics, clustering):
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
    skipped_process = 0

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

            c = characteristics[d]
            if c.is_from_bot:
                skipped_bot += 1
                skip = True
            if c.is_stable_review:
                skipped_stable += 1
                skip = True
            if not c.patches_linux:
                skipped_not_linux += 1
                skip = True
            if not c.is_first_patch_in_thread:
                skipped_not_first_patch += 1
                skip = True
            if c.process_mail:
                skipped_process += 1
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

    # That's the population that is relevant for this analysis
    population_relevant = upstreamed_patches | not_upstreamed_patches

    # Calculate ignored patches
    ignored_patches = {patch for patch in not_upstreamed_patches
                       if characteristics[patch].has_foreign_response == False}

    # Calculate ignored patches wrt to other patches in the cluster: A patch is
    # considered as ignored, if all related patches were ignoreed as well
    ignored_patches_related = {patch for patch in ignored_patches
                               if False not in [characteristics[x].has_foreign_response == False
                                                for x in clustering.get_downstream(patch)]}

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
    log.info('  Process mail: %u' % skipped_process)
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


def check_correct_maintainer_patch(c):
    # Metric: All lists + at least one maintainer per subsystem
    # needs to be addressed correctly
    #if (not c.mtrs_has_lists or c.mtrs_has_list_per_subsystem) and \
    #   (not c.mtrs_has_maintainers or c.mtrs_has_maintainer_per_subsystem):
    #    return True

    # Metric: At least one correct list + at least one correct maintainer
    #if (not c.mtrs_has_lists or c.mtrs_has_one_correct_list) and \
    #   (not c.mtrs_has_maintainers or c.mtrs_has_one_correct_maintainer):
    #    return True

    # Metric: One correct list + one maintainer per subsystem
    #if (not c.mtrs_has_lists or c.mtrs_has_one_correct_list) and c.mtrs_has_maintainer_per_subsystem:
    #    return True

    # Metric: One correct list
    #if (not c.mtrs_has_lists or has_one_correct_list):
    #    return True

    # Metric: One correct list or one correct maintainer
    if c.mtrs_has_lists and c.mtrs_has_one_correct_list:
        return True
    elif c.mtrs_has_maintainers and c.mtrs_has_one_correct_maintainer:
        return True
    if not c.mtrs_has_lists and not c.mtrs_has_maintainers:
        return c.mtrs_has_linux_kernel

    return False


def check_correct_maintainer(repo, characteristics, message_ids):
    correct_maintainer = dict()
    sum_lists = dict()
    sum_correct = dict()

    victims = set()
    for message_id in message_ids:
        c = characteristics[message_id]
        if c.is_first_patch_in_thread and c.patches_linux and \
           not c.is_stable_review and not c.is_from_bot and not c.process_mail:
            victims.add(message_id)
    message_ids = victims

    for message_id in message_ids:
        lists = repo.mbox.get_lists(message_id)
        for l in lists:
            if l not in sum_correct:
                sum_correct[l] = 0
            if l not in sum_lists:
                sum_lists[l] = 0
            sum_lists[l] += 1

        correct = check_correct_maintainer_patch(characteristics[message_id])
        if correct:
            for l in lists:
                sum_correct[l] += 1
        correct_maintainer[message_id] = correct

    correct = {message_id for message_id, value in correct_maintainer.items() if value == True}
    log.info('  Fraction of correctly addressed patches: %0.3f' %
             (len(correct) / len(message_ids)))

    for l in sum_lists.keys():
        log.info('  Fraction of correctly addressed patches on %s: %0.3f' %
                 (l, sum_correct[l] / sum_lists[l]))

    dump_messages(os.path.join(d_resources, 'maintainers_correct'), repo,
                  correct)
    dump_messages(os.path.join(d_resources, 'maintainers_incorrect'), repo,
                  message_ids - correct)


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


def load_pkl_and_update(filename, update_command):
    filename = f_pkl(filename)

    ret = None
    if os.path.isfile(filename):
        ret = pickle.load(open(filename, 'rb'))

    ret, changed = update_command(ret)
    if changed:
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

    def load_all_maintainers(ret):
        if ret is None:
            ret = dict()

        tags = {x[0] for x in repo.tags if not x[0].startswith('v2.6')}
        tags |= {x[0] for x in repo.tags if x[0].startswith('v2.6.39')}
        # WORKAROUND:
        #tags = {x[0] for x in repo.tags if x[0].startswith('v5.')}

        # Only load what's not already cached
        tags -= ret.keys()

        if len(tags) == 0:
            return ret, False

        global _repo
        _repo = repo
        p = Pool(processes=cpu_count())
        for tag, maintainers in tqdm(p.imap_unordered(load_maintainers, tags),
                                     total=len(tags), desc='MAINTAINERS'):
            ret[tag] = maintainers
        p.close()
        p.join()
        _repo = None

        return ret, True

    def load_characteristics(ret):
        if ret is None:
            ret = dict()

        missing = all_messages_in_time_window - ret.keys()
        if len(missing) == 0:
            return ret, False

        foo = load_linux_mail_characteristics(repo,
                                              missing,
                                              maintainers_version,
                                              clustering)

        return {**ret, **foo}, True

    log.info('Loading/Updating MAINTAINERS...')
    maintainers_version = load_pkl_and_update('maintainers', load_all_maintainers)

    log.info('Loading/Updating Linux patch characteristics...')
    characteristics = load_pkl_and_update('characteristics', load_characteristics)

    get_patch_origin(repo, characteristics, all_messages_in_time_window)

    log.info('Identify ignored patches...')
    get_ignored(repo, characteristics, clustering)

    log.info('Checking correct maintainers...')
    check_correct_maintainer(repo, characteristics, patches)

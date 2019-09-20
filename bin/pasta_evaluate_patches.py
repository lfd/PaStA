"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2019
Copyright (c) OTH Regensburg, 2019

Authors:
  Sebastian Duda <sebastian.duda@fau.de>
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import csv
import os
import pickle
import re

from logging import getLogger
from multiprocessing import Pool, cpu_count
from subprocess import call

from tqdm import tqdm

from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta.LinuxMailCharacteristics import load_linux_mail_characteristics

log = getLogger(__name__[-15:])

_repo = None
_config = None
_p = None

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')


def get_relevant_patches(characteristics):
    # First, we have to define the term 'relevant patch'. For our analysis, we
    # must only consider patches that either fulfil rule 1 or 2:
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
    #
    # Furthermore, only consider patches that actually patch Linux (~14% of all
    # patches on Linux MLs patch other projects). Then only consider patches
    # that are not for next, not from bots (there are a lot of bots) and that
    # are no 'process mails' (e.g., pull requests)

    relevant = set()

    all_patches = 0
    skipped_bot = 0
    skipped_stable = 0
    skipped_not_linux = 0
    skipped_no_patch = 0
    skipped_not_first_patch = 0
    skipped_process = 0
    skipped_next = 0

    for m, c in characteristics.items():
        skip = False
        all_patches += 1

        if not c.is_patch:
            skipped_no_patch += 1
            skip = True
        if not c.patches_linux:
            skipped_not_linux += 1
            skip = True
        if not c.is_first_patch_in_thread:
            skipped_not_first_patch += 1
            skip = True

        if c.is_from_bot:
            skipped_bot += 1
            skip = True
        if c.is_stable_review:
            skipped_stable += 1
            skip = True
        if c.process_mail:
            skipped_process += 1
            skip = True
        if c.is_next:
            skipped_next += 1
            skip = True

        if skip:
            continue

        relevant.add(m)

    log.info('')
    log.info('=== Calculation of relevant patches ===')
    log.info('All patches: %u' % all_patches)
    log.info('Skipped patches:')
    log.info('  No patch: %u' % skipped_no_patch)
    log.info('  Not Linux: %u' % skipped_not_linux)
    log.info('  Bot: %u' % skipped_bot)
    log.info('  Stable: %u' % skipped_stable)
    log.info('  Process mail: %u' % skipped_process)
    log.info('  Next: %u' % skipped_next)
    log.info('Relevant patches: %u' % len(relevant))

    return relevant


def get_ignored(characteristics, clustering, relevant):
    # Calculate ignored patches
    ignored_patches = {patch for patch in relevant if
                       not characteristics[patch].is_upstream and
                       not characteristics[patch].has_foreign_response}

    # Calculate ignored patches wrt to other patches in the cluster: A patch is
    # considered as ignored, if all related patches were ignoreed as well
    ignored_patches_related = \
        {patch for patch in ignored_patches if False not in
         [characteristics[x].has_foreign_response == False
          for x in (clustering.get_downstream(patch) & relevant)]}

    num_relevant = len(relevant)
    num_ignored_patches = len(ignored_patches)
    num_ignored_patches_related = len(ignored_patches_related)

    log.info('Found %u ignored patches' % num_ignored_patches)
    log.info('Fraction of ignored patches: %0.3f' %
             (num_ignored_patches / num_relevant))
    log.info('Found %u ignored patches (related)' % num_ignored_patches_related)
    log.info('Fraction of ignored related patches: %0.3f' %
            (num_ignored_patches_related / num_relevant))

    return ignored_patches, ignored_patches_related


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
    ret = None
    if os.path.isfile(filename):
        ret = pickle.load(open(filename, 'rb'))

    ret, changed = update_command(ret)
    if changed:
        pickle.dump(ret, open(filename, 'wb'))

    return ret


def dump_characteristics(characteristics, ignored, relevant, filename):
    with open(filename, 'w') as csv_file:
        csv_fields = ['id', 'from', 'recipients', 'lists', 'kv', 'rc',
                      'upstream', 'ignored', 'time', 'mtrs_correct']
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        for patch in sorted(relevant):
            c = characteristics[patch]

            tag = c.linux_version.split('-rc')
            kv = tag[0]
            rc = 0
            if len(tag) == 2:
                rc = int(tag[1])

            mail_from = c.mail_from[1]
            recipients = ' '.join(sorted(c.recipients))
            lists = ' '.join(sorted(c.lists))
            mtrs_correct = check_correct_maintainer_patch(c)

            row = {'id': patch,
                   'from': mail_from,
                   'recipients': recipients,
                   'lists' : lists,
                   'kv': kv,
                   'rc': rc,
                   'upstream': c.is_upstream,
                   'ignored': patch in ignored,
                   'time': c.date,
                   'mtrs_correct': mtrs_correct}

            writer.writerow(row)


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

        # Only load what's not yet cached
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

        missing = load_linux_mail_characteristics(repo,
                                                  missing,
                                                  maintainers_version,
                                                  clustering)

        return {**ret, **missing}, True

    log.info('Loading/Updating MAINTAINERS...')
    maintainers_version = load_pkl_and_update(config.f_maintainers_pkl,
                                              load_all_maintainers)

    log.info('Loading/Updating Linux patch characteristics...')
    characteristics = load_pkl_and_update(config.f_characteristics_pkl,
                                          load_characteristics)

    relevant = get_relevant_patches(characteristics)

    log.info('Identify ignored patches...')
    ignored_patches, ignored_patches_related = get_ignored(characteristics,
                                                           clustering,
                                                           relevant)

    dump_characteristics(characteristics, ignored_patches_related, relevant,
                         config.f_characteristics)

    call(['./R/evaluate_patches.R', config.d_rout, config.f_characteristics])

"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2019
Copyright (c) OTH Regensburg, 2019-2020

Authors:
  Sebastian Duda <sebastian.duda@fau.de>
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>
  Anmol Singh <anmol.singh@bmw.de>

This work is licensed under the terms of the GNU GPL, version 2. See
the COPYING file in the top-level directory.
"""

import anytree
import argparse
import csv
import pandas as pd
import pickle
import re

from itertools import product
from logging import getLogger
from subprocess import call

from pypasta.LinuxMaintainers import load_maintainers
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

    all_messages = 0
    skipped_bot = 0
    skipped_stable = 0
    skipped_not_linux = 0
    skipped_no_patch = 0
    skipped_not_first_patch = 0
    skipped_process = 0
    skipped_next = 0

    for m, c in characteristics.items():
        skip = False
        all_messages += 1

        if not c.is_patch:
            skipped_no_patch += 1
            continue

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
    log.info('All messages: %u' % all_messages)
    log.info('  No patches: %u' % skipped_no_patch)
    log.info('Skipped patches:')
    log.info('  Not Linux: %u' % skipped_not_linux)
    log.info('  Bot: %u' % skipped_bot)
    log.info('  Stable: %u' % skipped_stable)
    log.info('  Process mail: %u' % skipped_process)
    log.info('  Next: %u' % skipped_next)
    log.info('Relevant patches: %u' % len(relevant))

    return relevant


def load_characteristics_and_maintainers(config, clustering):
    """
    This routine loads characteristics for ALL mails in the time window config.mbox_timewindow, and loads multiple
    instances of maintainers for the the patches of the clustering.

    Returns the characteristics and maintainers_version
    """
    repo = config.repo
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    tags = {repo.linux_patch_get_version(repo[x]) for x in clustering.get_downstream()}
    maintainers_version = load_maintainers(config, tags)
    characteristics = \
        load_linux_mail_characteristics(config, maintainers_version, clustering,
                                        all_messages_in_time_window)

    return characteristics, maintainers_version


def prepare_ignored_patches(config, clustering):
    def _get_kv_rc(linux_version):
        tag = linux_version.split('-rc')
        kv = tag[0]
        rc = 0
        if len(tag) == 2:
            rc = int(tag[1])

        return kv, rc

    repo = config.repo
    characteristics, _ = load_characteristics_and_maintainers(config, clustering)
    relevant = get_relevant_patches(characteristics)

    log.info('Identify ignored patches...')
    # Calculate ignored patches
    ignored_patches = {patch for patch in relevant if
                       not characteristics[patch].is_upstream and
                       not characteristics[patch].has_foreign_response}

    # Calculate ignored patches wrt to other patches in the cluster: A patch is
    # considered as ignored, if all related patches were ignored as well
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

    log.info('Dumping characteristics...')
    ignored_target = ignored_patches_related
    # Alternative analysis:
    #ignored_target = ignored_patches

    with open(config.f_characteristics, 'w') as csv_file:
        csv_fields = ['id', 'from', 'list', 'list_matches_patch', 'kv', 'rc',
                      'ignored', 'time']
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        for message_id in sorted(relevant):
            c = characteristics[message_id]
            kv, rc = _get_kv_rc(c.linux_version)
            mail_from = c.mail_from[1]

            for list in repo.mbox.get_lists(message_id):
                list_matches_patch = c.list_matches_patch(list)

                row = {'id': message_id,
                       'from': mail_from,
                       'list': list,
                       'list_matches_patch': list_matches_patch,
                       'kv': kv,
                       'rc': rc,
                       'ignored': message_id in ignored_target,
                       'time': c.date,
                       }

                writer.writerow(row)

    log.info('Calling R...')
    call(['./analyses/ignored_patches.R', config.d_rout, config.f_characteristics])


def prepare_off_list_patches():
    pass


def prepare_patch_review(config, clustering):
    repo = config.repo
    mbox = repo.mbox
    threads = mbox.load_threads()

    characteristics, _ = load_characteristics_and_maintainers(config, clustering)
    relevant = get_relevant_patches(characteristics)

    df_melt_upstream = list()
    for d, u in clustering.iter_split():
        d &= relevant
        d = d or {'_'}
        u = u or {'_'}
        for patch, commit in product(d, u):
            df_melt_upstream.append({'patch_id': patch,
                                     'upstream': commit})

    df_melt_upstream = pd.DataFrame(df_melt_upstream)
    df_melt_upstream.to_csv('/tmp/patch_denorm_upstream.csv', index=False)


    df_denorm_responses = list()
    for d, _ in clustering.iter_split():
        d &= relevant
        for patch_id in d:
            subthread = threads.get_thread(patch_id, subthread=True)
            for node in anytree.PreOrderIter(subthread,
                              filter_=lambda node: node.name != patch_id):
                df_denorm_responses.append({
                    'patch_id': patch_id,
                    'response_author': mbox.get_messages(node.name)[0]['from'],
                    'response_parent': node.parent.name,
                    'response_msg_id': node.name,
                })
    df_denorm_responses = pd.DataFrame(df_denorm_responses)
    df_denorm_responses.to_csv('/tmp/patch_denorm_responses.csv', index=False)


def prepare_evaluation(config, argv):
    parser = argparse.ArgumentParser(prog='prepare_evaluation',
                                     description='aggregate commit and patch info')

    parser.add_argument('--ignored',
                        action='store_const',
                        const='ignored',
                        dest='mode',
                        help='prepare data for patch analysis \n'
                             'prepare data for ignored patch analysis \n'
                        )

    parser.add_argument('--off-list',
                        action='store_const',
                        const='off-list',
                        dest='mode',
                        help='prepare data for off-list patch analysis \n')

    parser.add_argument('--review',
                        action='store_const',
                        const='review',
                        dest='mode',
                        help='prepare data for patch review analysis \n')

    analysis_option = parser.parse_args(argv)

    if not analysis_option.mode:
        parser.error("No action requested, one of --ignored, --off-list, or --review must be given")

    if config.mode != config.Mode.MBOX:
        log.error("Only works in Mbox mode!")
        return -1

    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()

    if analysis_option.mode == 'ignored':
        prepare_ignored_patches(config, clustering)

    elif analysis_option.mode == 'off-list':
        prepare_off_list_patches()

    else:
        prepare_patch_review(config, clustering)

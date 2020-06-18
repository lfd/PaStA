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

import argparse
import csv
import dask.dataframe as dd
import flat_table
import os
import pandas as pd
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


def load_all_maintainers(ret, repo):
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


def prepare_ignored_patches(config, repo, clustering):
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    def _get_ignored(characteristics, clustering, relevant):
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

    def _load_characteristics(ret, repo):
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

    def _load_pkl_and_update(filename, update_command, repo):
        ret = None
        if os.path.isfile(filename):
            ret = pickle.load(open(filename, 'rb'))

        ret, changed = update_command(ret, repo)
        if changed:
            pickle.dump(ret, open(filename, 'wb'))

        return ret

    def _get_kv_rc(linux_version):
        tag = linux_version.split('-rc')
        kv = tag[0]
        rc = 0
        if len(tag) == 2:
            rc = int(tag[1])

        return kv, rc

    def _dump_characteristics(repo, characteristics, ignored, relevant, filename):
        with open(filename, 'w') as csv_file:
            csv_fields = ['id', 'from', 'list', 'list_matches_patch', 'kv', 'rc',
                          'ignored', 'time']
            writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
            writer.writeheader()

            for message_id in sorted(relevant):
                c = characteristics[message_id]
                kv, rc = _get_kv_rc(c.linux_version)
                mail_from = c.mail_from[1]

                for list in repo.mbox.get_lists(message_id):
                    list_matches_patch = False
                    for subsys in c.maintainers.values():
                        lists = subsys[0]
                        if list in lists:
                            list_matches_patch = True
                            break

                    row = {'id': message_id,
                           'from': mail_from,
                           'list': list,
                           'list_matches_patch': list_matches_patch,
                           'kv': kv,
                           'rc': rc,
                           'ignored': message_id in ignored,
                           'time': c.date,
                           }

                    writer.writerow(row)

    log.info('Loading/Updating MAINTAINERS...')
    maintainers_version = _load_pkl_and_update(config.f_maintainers_pkl,
                                               load_all_maintainers, repo)

    log.info('Loading/Updating Linux patch characteristics...')
    characteristics = _load_pkl_and_update(config.f_characteristics_pkl,
                                           _load_characteristics, repo)

    relevant = get_relevant_patches(characteristics)

    log.info('Identify ignored patches...')
    ignored_patches, ignored_patches_related = _get_ignored(characteristics,
                                                            clustering,
                                                            relevant)

    _dump_characteristics(repo, characteristics, ignored_patches_related,
                          relevant, config.f_characteristics)

    call(['./analyses/ignored_patches.R', config.d_rout, config.f_characteristics])


def prepare_off_list_patches():
    pass


def prepare_patch_review(config, repo, clustering):
    threads = repo.mbox.load_threads()
    clusters = list(clustering.iter_split())

    def _load_responses_dict(msg_id, response_list):
        queue = [msg_id]
        seen = []
        while queue:
            next_msg = queue.pop(0)
            if next_msg not in seen:
                seen.append(next_msg)
                try:
                    next_msg_responses = list(threads.reply_to_map[next_msg])
                    queue.extend(next_msg_responses)
                    for resp in next_msg_responses:
                        resp_dict = {'parent': next_msg, 'resp_msg_id': resp, 'message': repo.mbox.get_raws(resp)}
                        response_list.append(resp_dict)
                except KeyError:
                    log.info("The email {} has no response".format(next_msg))
                    continue
        return

    clusters_responses = []
    for d, u in clusters:
        # Handle upstream commits without patches
        if not d:
            cluster_dict = {}
            try:
                cluster_dict['cluster_id'] = clustering.get_cluster(next(iter(u)))
                cluster_dict['upstream'] = u
                cluster_dict['patch_id'] = None
                cluster_dict['responses'] = None
                clusters_responses.append(cluster_dict)
            except KeyError:
                log.warning("No downstream or upstream found, bad entry?...Skipping")
        for patch_id in d:
            # Handle entries with patches
            cluster_dict = {'cluster_id': clustering.get_cluster(patch_id), 'patch_id': patch_id, 'upstream': u}

            # Add responses for the patch
            response_lst = []
            _load_responses_dict(patch_id, response_lst)
            cluster_dict['responses'] = response_lst
            clusters_responses.append(cluster_dict)

    with open(config.f_responses_pkl, 'wb') as handle:
        pickle.dump(clusters_responses, handle, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Done writing response info for {} patch/commit entries!".format(len(clusters)))
    log.info("Total clusters found by pasta: {}".format(len(clusters)))


def pre_process_response_data(config):
    pass


def merge_pre_processed_response_dfs():
    pass


def filter_bots():
    pass


def prepare_evaluation(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='aggregate commit and patch info')

    parser.add_argument('--ignored',
                        action='store_true',
                        default=False,
                        help='prepare data for patch analysis \n'
                             'prepare data for ignored patch analysis \n'
                        )

    parser.add_argument('--offlist',
                        action='store_true',
                        default=False,
                        help='prepare data for off-list patch analysis \n')

    parser.add_argument('--review',
                        default=None,
                        choices=['prepare', 'preprocess', 'merge', 'filter'],
                        help='prepare data for patch review analysis \n')

    analysis_option = parser.parse_args(argv)

    if len(argv) == 0:
        parser.error("No action requested, one of --ignored, --off-list, or --review must be given")

    if config.mode != config.Mode.MBOX:
        log.error("Only works in Mbox mode!")
        return -1

    repo = config.repo
    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()

    if analysis_option.ignored:
        prepare_ignored_patches(config, repo, clustering)

    elif analysis_option.offlist:
        prepare_off_list_patches()

    else:
        if analysis_option.review == 'prepare':
            prepare_patch_review(config, repo, clustering)
        elif analysis_option.review == 'preprocess':
            pre_process_response_data(config)
        elif analysis_option.review == 'merge':
            merge_pre_processed_response_dfs()
        else:
            filter_bots()


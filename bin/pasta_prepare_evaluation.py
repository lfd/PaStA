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
import dask.dataframe as dd
import email
import flat_table
import numpy as np
import os
import pandas as pd
import pickle
import re
import sys

from ast import literal_eval
from logging import getLogger
from subprocess import call

from pypasta import email_get_header_normalised, email_get_from
from pypasta.LinuxMaintainers import load_maintainers
from pypasta.LinuxMailCharacteristics import load_linux_mail_characteristics

from analyses import response_analysis

sys.path.append(os.path.join(os.path.abspath(os.pardir), 'analyses'))

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


def prepare_ignored_patches(config, clustering):
    def _get_kv_rc(linux_version):
        tag = linux_version.split('-rc')
        kv = tag[0]
        rc = 0
        if len(tag) == 2:
            rc = int(tag[1])

        return kv, rc

    repo = config.repo
    repo.mbox.load_threads()

    patches = set()
    upstream = set()
    for d, u in clustering.iter_split():
        patches |= d
        upstream |= u

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    tags = {x[0] for x in repo.tags if not x[0].startswith('v2.6')}
    tags |= {x[0] for x in repo.tags if x[0].startswith('v2.6.39')}
    maintainers_version = load_maintainers(config, tags)
    characteristics = \
        load_linux_mail_characteristics(config, maintainers_version, clustering,
                                        all_messages_in_time_window)

    relevant = get_relevant_patches(characteristics)

    log.info('Identify ignored patches...')
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
    threads = repo.mbox.load_threads()
    clusters = list(clustering.iter_split())
    targets_characteristics = set()
    clusters_responses = list()

    for cluster_id, (d, u) in enumerate(clusters):
        targets_characteristics |= d

        # Handle clusters w/o patches, i.e., upstream commits
        if not d:
            clusters_responses.append({'cluster_id': cluster_id,
                                       'upstream': u,
                                       'patch_id':  None,
                                       'responses': None})
            continue

        # Handle regular clusters with patches
        for patch_id in d:
            # Add responses for the patch
            subthread = threads.get_thread(patch_id, subthread=True)

            responses = list()
            # Iterate over all subnodes, but omit the root-node (patch_id)
            for node in anytree.PreOrderIter(subthread, filter_=lambda node: node.name != patch_id):
                targets_characteristics.add(node.name)
                response_author = repo.mbox.get_messages(node.name)[0]['from']
                responses.append({'resp_msg_id': node.name,
                                  'parent': node.parent.name,
                                  'response_author': response_author})

            clusters_responses.append({'cluster_id': cluster_id,
                                       'patch_id': patch_id,
                                       'upstream': u,
                                       'responses': responses})

    clusters_responses = pd.DataFrame(clusters_responses)

    with open(config.f_responses_pkl, 'wb') as handle:
        pickle.dump(clusters_responses, handle, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Done writing response info for {} patch/commit entries!".format(len(clusters)))
    log.info("Total clusters found by pasta: {}".format(len(clusters)))

    load_linux_mail_characteristics(config, None, clustering,
                                    targets_characteristics)


def pre_process_response_data(config):
    # Load responses dict into dataframe, preliminary processing, indexing

    with open(config.f_responses_pkl, 'rb') as handle:
        data = pickle.load(handle)

    response_df = pd.DataFrame(data)
    log.info("Done reading input in pandas dataframe")

    # Convert set to list
    response_df['upstream'] = response_df['upstream'].map(list)

    response_df.index.name = "idx"

    response_df.fillna({'patch_id': '_'}, inplace=True)
    log.info("Filled NA for patch_id")

    response_df.set_index(['patch_id'], append=True, inplace=True)
    log.info("Done setting index for response_df")

    # Denormalize
    df_melt_responses = pd.melt(response_df.responses.apply(pd.Series).reset_index(),
                                id_vars=['idx', 'patch_id'],
                                value_name='responses').sort_index()

    df_melt_responses.drop('variable', axis=1, inplace=True)

    log.info("melt_responses_shape {}".format(df_melt_responses.shape))

    df_denorm_responses = flat_table.normalize(df_melt_responses, expand_dicts=True, expand_lists=True)
    df_denorm_responses.drop('index', axis=1, inplace=True)
    df_denorm_responses.drop_duplicates(inplace=True)
    log.info("Computed de-normalized responses, writing to disk...")

    df_denorm_responses.to_csv(config.f_denorm_responses, index=False)
    log.info("Processed responses!")

    df_melt_upstream = pd.melt(response_df.upstream.apply(pd.Series).reset_index(),
                               id_vars=['idx', 'patch_id'],
                               value_name='upstream').sort_index()

    df_melt_upstream.drop('variable', axis=1, inplace=True)
    df_melt_upstream.drop_duplicates(inplace=True)

    df_melt_upstream.to_csv(config.f_denorm_upstream, index=False)
    log.info("Processed upstream!")
    log.info("Finished processing")


def merge_pre_processed_response_dfs(config):
    def try_literal_eval(s):
        try:
            return literal_eval(s)
        except ValueError:
            return s

    def _get_message_field(msg, field):
        if not (np.all(pd.isnull(msg))):
            return email.message_from_bytes(msg)[field]
        else:
            return None

    dd1 = dd.read_csv(config.f_denorm_responses, blocksize=1e9, dtype={"idx ": "int32", "patch_id ": "category",
                                                                       "responses.resp_msg_id": "category",
                                                                       "responses.parent": "category"})

    dd1 = dd1.set_index(['idx'])

    dd2 = dd.read_csv(config.f_denorm_upstream, blocksize=1e9, dtype={"idx ": "int32", "patch_id ": "category",
                                                                      "upstream": "category"})

    dd2 = dd2.set_index(['idx'])

    df_dask_final = dd.merge(dd1, dd2, left_index=True, right_index=True, how='left') \
        .drop(['patch_id_y'], axis=1) \
        .reset_index(drop=True) \
        .rename(columns={"patch_id_x": "patch_id"})

    df_dask_final.to_csv("df_dask_final.csv", single_file=True)

    final = dd.read_csv("df_dask_final.csv", blocksize=50e7, dtype={"idx ": "int32", "patch_id ": "category",
                                                                    "responses.resp_msg_id": "category",
                                                                    "responses.parent": "category",
                                                                    "upstream": "category"}).drop('Unnamed: 0', axis=1)

    print("Final shape with possible duplicate rows{}".format(final.shape))
    final.drop_duplicates(inplace=True)

    # Convert to pandas
    df_pd_final = final.compute()

    # Remove rows with no patch and other infos
    index_names = df_pd_final[(df_pd_final['patch_id'] == '_') & (df_pd_final['responses.message'].isna()) &
                              (df_pd_final['upstream'].isna())].index
    df_pd_final.drop(index_names, inplace=True)

    print("Final shape after removing duplicates {}".format(final.shape))

    # df_pd_final.to_csv(config.f_merged_responses_upstream, index=False)
    # print("Finished writing de-duplicated pandas merged dataframe to disk")

    final = dd.from_pandas(df_pd_final, npartitions=20)

    final['responses.message'] = final['responses.message'].map(try_literal_eval)

    final.reset_index().rename(columns={'index': 'idx'}).compute()

    final['response_author'] = final['responses.message'].map(lambda x: _get_message_field(x, 'from'),
                                                              meta=pd.Series([], dtype=object, name='x'))

    log.info("Unique response authors {}".format(final['response_author'].nunique().compute(num_workers=20)))

    final.to_csv(config.f_responses_authors, single_file=True)


def _is_response_from_bot(message_id):
    message = _repo.mbox.get_messages(message_id)[0]
    email = email_get_from(message)[1].lower()
    bots = ['tip-bot2@linutronix.de', 'tipbot@zytor.com', 'noreply@ciplatform.org', 'syzbot',
            'syzkaller.appspotmail.com']
    potential_bots = ['broonie@kernel.org', 'lkp@intel.com']
    subject = email_get_header_normalised(message, 'subject')
    uagent = email_get_header_normalised(message, 'user-agent')
    xmailer = email_get_header_normalised(message, 'x-mailer')

    if email in bots:
        return message_id, True
    elif email in potential_bots and \
            email_get_header_normalised(message, 'x-patchwork-hint') == 'ignore':
        return message_id, True
    elif email in potential_bots and subject.startswith('applied'):
        return message_id, True
    elif LinuxMailCharacteristics.REGEX_GREG_ADDED.match(subject):
        return message_id, True
    # AKPM's bot. AKPM uses s-nail for automated mails, and sylpheed for
    # all other mails. That's how we can easily separate automated mails
    # from real mails.
    elif email == 'akpm@linux-foundation.org' and 's-nail' in uagent:
        return message_id, True
    elif xmailer == 'tip-git-log-daemon':
        return message_id, True
    else:
        return message_id, False


def filter_bots(config, clustering):
    repo = config.repo
    repo.mbox.load_threads()

    final = dd.read_csv(config.f_responses_authors, blocksize=50e7,
                        dtype={"idx ": "int32",
                               "patch_id ": "category",
                               "responses.resp_msg_id": "category",
                               "responses.parent": "category",
                               "upstream": "category",
                               "response_author": "category"}).drop('Unnamed: 0', axis=1)

    log.info("Finished reading dask dataframe {}".format(config.f_responses_authors))

    # Discard null patches (coming from upstreams that were not mapped to any patch emails)
    unique_patches = set(final.patch_id.unique().compute())
    unique_patches.discard('_')

    patch_characteristics = load_linux_mail_characteristics(config, None, clustering, unique_patches)

    # Consider only relevant patches (as per given definition of relevance)
    relevant_patches = get_relevant_patches(patch_characteristics)
    final_filtered_1 = final[final['patch_id'].isin(relevant_patches)]

    # Filter responses -- only responses to the patch itself count as a response, and not the rest of the thread emails
    final_filtered_2 = final_filtered_1[final_filtered_1['patch_id'] == final_filtered_1['responses.parent']]

    global _repo
    _repo = repo

    p1 = Pool(processes=int(cpu_count()), maxtasksperchild=1)
    response_to_bot = p1.map(_is_response_from_bot, list(final_filtered_2['responses.resp_msg_id'].unique().compute()),
                            chunksize=1000)
    p1.close()
    p1.join()

    _repo = None

    response_bot_df = pd.DataFrame(response_to_bot, columns=['responses.resp_msg_id', 'response_is_bot'])

    final_filtered_2 = dd.merge(final_filtered_2, response_bot_df, how='left', on=['responses.resp_msg_id'])

    if 'response_is_bot_x' in final_filtered_2.columns:
        final_filtered_2 = final_filtered_2.drop(['response_is_bot_x'], axis=1) \
            .rename(columns={"response_is_bot_y": "response_is_bot"})

    # Filter out responses from bots
    final_filtered_3 = final_filtered_2[final_filtered_2['response_is_bot'] != True]

    final_filtered_3.to_csv(config.f_filtered_responses, single_file=True)

    log.info("Written filtered response dataframe to disk, Done!")


def prepare_evaluation(config, argv):
    parser = argparse.ArgumentParser(prog='prepare_evaluation',
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
                        choices=['prepare', 'preprocess', 'merge', 'filter', 'analyze'],
                        help='prepare data for patch review analysis \n')

    analysis_option = parser.parse_args(argv)

    if len(argv) == 0:
        parser.error("No action requested, one of --ignored, --off-list, or --review must be given")

    if config.mode != config.Mode.MBOX:
        log.error("Only works in Mbox mode!")
        return -1

    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()

    if analysis_option.ignored:
        prepare_ignored_patches(config, clustering)

    elif analysis_option.offlist:
        prepare_off_list_patches()

    else:
        if analysis_option.review == 'prepare':
            prepare_patch_review(config, clustering)
        elif analysis_option.review == 'preprocess':
            pre_process_response_data(config)
        elif analysis_option.review == 'merge':
            merge_pre_processed_response_dfs(config)
        elif analysis_option.review == 'filter':
            filter_bots(config, clustering)
        else:
            response_analysis.analyse_responses(config.f_filtered_responses)

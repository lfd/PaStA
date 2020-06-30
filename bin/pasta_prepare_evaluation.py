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

from analyses import response_analysis
from pypasta.LinuxMaintainers import LinuxMaintainers
from pypasta import LinuxMailCharacteristics, load_linux_mail_characteristics

import argparse
from ast import literal_eval
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

from logging import getLogger

from multiprocessing import Pool, cpu_count
from subprocess import call

from tqdm import tqdm

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


def _is_response_from_bot(message):
    lmc = LinuxMailCharacteristics(_repo, None, None, message)
    return message, lmc.is_from_bot


def filter_bots(config, repo, clustering):
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
            merge_pre_processed_response_dfs(config)
        elif analysis_option.review == 'filter':
            filter_bots(config, repo, clustering)
        else:
            response_analysis.analyse_responses(config.f_filtered_responses)

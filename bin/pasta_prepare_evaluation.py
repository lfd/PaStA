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
import chardet
import csv
import dask.dataframe as dd
import email
import flat_table
import os
import pandas as pd
import pickle
import re
import sys

from fuzzywuzzy import fuzz
from logging import getLogger
from multiprocessing import Pool, cpu_count
from subprocess import call

from pypasta.LinuxMaintainers import load_maintainers
from pypasta import LinuxMailCharacteristics, load_linux_mail_characteristics, email_get_from

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

        if c.is_from_bot[0]:
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

    tags = {repo.linux_patch_get_version(repo[x]) for x in patches}
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
    # ignored_target = ignored_patches

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
                                       'patch_id': None,
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
    # Idea: We do the following transformation in the preprocess step:
    # We split the response_df into two parts: responses and upstream. This split is necessary
    # for the following reasons:
    # 1. responses and upstream columns have different datatypes: dict vs set, and hence need to be handled differently.
    # 2. for bigger datasets, this also keeps the memory needs in check: we merge these two parts in the merge step,
    # and hence the intermediate (huge) dataframes are not in memory anymore at one time making it computationally
    # feasible given the systems' constraints with decent performance.
    # The two parts which are output after this step: f_denorm_responses and f_denorm_upstream, need to be merged
    # back together later such that the resulting dataframe has the following property:
    # One row for each unique patch_id, response (and response details, e.g. parent), and upstream.
    #
    # Example: Entry p1, u1, u2 in patch-groups, with two responses r1, r2 for p1
    #                               where p1 is a patch with two linked upstream commits, u1 and u2
    # Denormalizing responses would yield the following two rows -
    #               p1, r1
    #               p1, r2
    # Denormalizing upstream would yield the following two rows -
    #               p1, u1
    #               p1, u2
    # The merge on patch id in the next step would then yield the following rows -
    #               p1, r1, u1
    #               p1, r2, u1
    #               p1, r1, u2
    #               p1, r2, u2
    # Advantage of such a data transformation: possibility to aggregate a variety of statistics, e.g.:
    # Patch to responses, and all the details for that response (authors, various email tags, message details
    # like length etc.), upstream to responses (and response characteristics as before), upstream to patch details, etc.
    #
    # Index: Merge works efficiently when we join on an index.
    #

    with open(config.f_responses_pkl, 'rb') as handle:
        response_df = pickle.load(handle)

    num_clusters = response_df.cluster_id.nunique()

    # Fill null patch ids with a value '_'
    response_df.fillna({'patch_id': '_'}, inplace=True)
    log.info("Filled NA for patch_id")

    num_patch_ids = response_df.patch_id.nunique()

    # Create a MultiIndex (cluster_id, patch_id)
    # This is a decision for the following reasons:
    # 1. patch_id cannot uniquely identify a row, e.g. when it is null ('_')
    # 2. Many analysis are easier with MultiIndex, without needing a groupby
    # 3. id_vars for melt
    response_df.set_index(['cluster_id', 'patch_id'], inplace=True)
    log.info("Done setting index for response_df")

    # Denormalize responses and upstream

    # Denormalize responses
    # Pandas melt is used to bring the data in the given de-normalized form.
    # reset_index operation preserves the index as a column, which otherwise could be lost
    df_melt_responses = pd.melt(response_df.responses.apply(pd.Series).reset_index(),
                                id_vars=['cluster_id', 'patch_id'],
                                value_name='responses').sort_index()

    df_melt_responses.drop('variable', axis=1, inplace=True)

    log.info("melt_responses_shape {}".format(df_melt_responses.shape))

    df_denorm_responses = flat_table.normalize(df_melt_responses, expand_dicts=True, expand_lists=True)
    df_denorm_responses.drop('index', axis=1, inplace=True)
    df_denorm_responses.drop_duplicates(subset=['responses.resp_msg_id', 'patch_id', 'cluster_id'], inplace=True)
    log.info("Computed de-normalized responses, writing to disk...")

    df_denorm_responses.to_csv(config.f_denorm_responses, index=False)
    log.info("Processed responses!")

    # Denormalize upstream

    # Convert set to list: This is necessary to apply pd.Series for converting set type column to individual rows
    response_df['upstream'] = response_df['upstream'].map(list)

    df_melt_upstream = pd.melt(response_df.upstream.apply(pd.Series).reset_index(),
                               id_vars=['cluster_id', 'patch_id'],
                               value_name='upstream').sort_index()

    df_melt_upstream.drop('variable', axis=1, inplace=True)
    df_melt_upstream.drop_duplicates(subset=['cluster_id', 'patch_id', 'upstream'], inplace=True)
    df_melt_upstream.dropna(subset=['upstream'], inplace=True)

    df_melt_upstream.to_csv(config.f_denorm_upstream, index=False)
    log.info("Processed upstream!")

    log.info(" ---------------- Data summary ---------------- ")
    log.info("Number of clusters: {}".format(num_clusters))
    log.info("Number of patch_ids (including NaN): {}".format(num_patch_ids))
    log.info("Number of upstream commits: {}".format(df_melt_upstream.upstream.nunique()))
    log.info(" ------------------------------------------------ ")


    log.info("Finished processing")


def merge_pre_processed_response_dfs(config):

    dd1 = dd.read_csv(config.f_denorm_responses, blocksize=1e9, dtype={"cluster_id": "int32",
                                                                       "patch_id ": "category",
                                                                       "responses.resp_msg_id": "category",
                                                                       "responses.parent": "category"})

    dd1 = dd1.set_index(['cluster_id'])

    dd2 = dd.read_csv(config.f_denorm_upstream, blocksize=1e9, dtype={"cluster_id": "int32",
                                                                      "patch_id ": "category",
                                                                      "upstream": "category"})

    dd2 = dd2.set_index(['cluster_id'])

    df_dask_final = dd.merge(dd1, dd2, left_index=True, right_index=True, how='outer') \
        .drop(['patch_id_y'], axis=1) \
        .reset_index() \
        .rename(columns={"patch_id_x": "patch_id"})

    df_dask_final.to_csv("df_dask_final.csv", single_file=True)

    final = dd.read_csv("df_dask_final.csv", blocksize=50e7, dtype={"cluster_id": "int32",
                                                                    "patch_id ": "category",
                                                                    "responses.resp_msg_id": "category",
                                                                    "responses.parent": "category",
                                                                    "upstream": "category"}).drop('Unnamed: 0', axis=1)

    print("Final shape with possible duplicate rows{}".format(final.shape))
    final.drop_duplicates(subset=['responses.resp_msg_id', 'upstream', 'patch_id', 'cluster_id'], inplace=True)

    # Convert to pandas
    df_pd_final = final.compute()

    print("Final shape after removing duplicates {}".format(final.shape))

    final = dd.from_pandas(df_pd_final, npartitions=20)

    final.reset_index().rename(columns={'index': 'idx'}).compute()

    final.to_csv(config.f_responses, single_file=True)


def _is_response_from_bot(message):
    lmc = LinuxMailCharacteristics(_repo, None, None, message)
    flag, botname = lmc.is_from_bot
    return message, flag, botname


def parseaddr_unicode(addr) -> (str, str):

    name, e_mail = addr
    name_list = []
    if name:
        name = name.strip()

        for decoded_string, charset in email.header.decode_header(name):
            if charset is not None:

                try:
                    if isinstance(decoded_string, bytes):
                        name = decoded_string.decode(charset or 'utf-8')
                    else:
                        name = str(decoded_string, 'utf-8', errors='ignore')
                except UnicodeDecodeError:
                    encoding = chardet.detect(decoded_string)['encoding']
                    try:
                        name = decoded_string.decode(encoding=encoding, errors='ignore')
                    except TypeError:
                        name = str(decoded_string, 'utf-8', errors='ignore')
            else:
                name = str(decoded_string)
            name_list.append(name)

    final_name = u''.join(name_list)
    return final_name, e_mail


def get_patch_author(message, repo):
    try:
        msg = repo.mbox.get_messages(message)[0]
        return parseaddr_unicode(email_get_from(msg))
    except Exception as e:
        log.error(e)
        return email_get_from(message)


def check_person_duplicates(patch_id, resp_msg_id, author1, author2):
    try:
        name1, email1 = author1
        name2, email2 = author2
        if email1 == email2:
            return True
        if name1 == name2:
            return True
        return fuzz.token_sort_ratio(name1, name2) >= 80
    except Exception as e:
        log.error(e)
        log.error("Error parsing authors for patch id {} and response {}: author1 {} and author2 {}"
                 .format(patch_id, resp_msg_id, author1, author2))
        return False


def filter_bots(config, clustering):
    repo = config.repo
    repo.mbox.load_threads()

    final = dd.read_csv(config.f_responses, blocksize=50e7,
                        dtype={"cluster_id": "int32",
                               "upstream": "category",
                               "response_author": "category"}).drop('Unnamed: 0', axis=1)

    log.info("Finished reading dask dataframe {}".format(config.f_responses))

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

    response_bot_df = pd.DataFrame(response_to_bot, columns=['responses.resp_msg_id', 'response_is_bot', 'bot_name'])

    _repo = None

    final_filtered_2 = dd.merge(final_filtered_2, response_bot_df, how='left', on=['responses.resp_msg_id'])

    if 'response_is_bot_x' in final_filtered_2.columns:
        final_filtered_2 = final_filtered_2.drop(['response_is_bot_x'], axis=1) \
            .rename(columns={"response_is_bot_y": "response_is_bot"})

    # Remove duplicate rows with response message id, upstream, and patch_id (artifact of denormalization?)
    final_dedup = final_filtered_2.drop_duplicates(subset=['responses.resp_msg_id', 'upstream', 'patch_id'],
                                                   keep='first')

    # Rename some columns, removing the 'responses.' prefix to simplify dataframe Series ops
    new_columns = ['cluster_id', 'patch_id', 'response_author', 'resp_parent', 'resp_msg_id', 'upstream', 'response_is_bot',
                   'bot_name']
    final_dedup = final_dedup.rename(columns=dict(zip(final_dedup.columns, new_columns)))

    final_dedup['patch_author'] = final_dedup['patch_id'].map(lambda x: get_patch_author(x, repo),
                                                              meta=pd.Series([], dtype=object, name='x'))

    final_dedup['responder'] = final_dedup['resp_msg_id'].map(lambda x: get_patch_author(x, repo),
                                                              meta=pd.Series([], dtype=object, name='x'))

    # This flag could detect authors responding themselves to the patches, e.g., responses to patches as rest
    # of the patch series (spotted often this case)
    final_dedup['self_response'] = final_dedup.map_partitions(lambda df: df.apply(
        (lambda row: check_person_duplicates(row.patch_id, row.resp_msg_id, row.patch_author, row.responder)),
        axis=1), meta=pd.Series([], dtype=object, name='row'))

    final_dedup.to_csv(config.f_filtered_responses, single_file=True)

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

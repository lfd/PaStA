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
import csv
import pickle
import re

from logging import getLogger
from subprocess import call
from tqdm import tqdm

from pypasta import *

log = getLogger(__name__[-15:])

_repo = None
_config = None

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
    skipped_not_project = 0
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

        if not c.patches_project:
            skipped_not_project += 1
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
    log.info('  Patches other project: %u' % skipped_not_project)
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


def prepare_process_characteristics(config, clustering):
    repo = config.repo

    relevant_releases = [(tag, date.strftime('%Y-%m-%d')) for tag, date in repo.tags if
                     config.mbox_mindate < date.replace(tzinfo=None) < config.mbox_maxdate and
                     '-rc' not in tag]
    with open(config.f_releases, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['release', 'date'])
        writer.writeheader()
        for release, date in relevant_releases:
            writer.writerow({'release': release,
                             'date': date})

    characteristics, maintainers_version = load_characteristics_and_maintainers(config, clustering)
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

    csv_fields = ['id', # The message-id of the patch
                  'from', # Who sent the patch?
                  'time', # When was the patch sent?
                  'type', # The type of the patch
                  'version', # What's the closest kernel version?
                  'list', # On which list was it sent to? (Multiple csv-entries for multiple lists!)
                  'list.matches_patch', # Does that list match to what MAINTAINERS tells us?
                  'ignored', # Was the patch ignored? See definition above.
                  'committer', # Who committed the patch? (Can be None. If committer != None -> ignored = False)
                  'committer.correct', # Is the committer a valid committer according to MAINTAINERS?
    ]

    with open(config.f_characteristics, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        for message_id in tqdm(sorted(clustering.get_downstream())):
            c = characteristics[message_id]
            mail_from = c.mail_from[1]

            ignored = None
            if message_id in relevant:
                ignored = message_id in ignored_target

            # Dump an entry for each list the patch was sent to. This allows
            # for grouping by mailing lists.
            for ml in repo.mbox.get_lists(message_id):
                list_matches_patch = c.list_matches_patch(ml)
                row = {'id': message_id,
                       'from': mail_from,
                       'time': c.date,
                       'version': c.version,
                       'type': c.type.value,
                       'list': ml,
                       'list.matches_patch': list_matches_patch,
                       'ignored': ignored,
                       'committer': c.committer,
                       'committer.correct': c.integrated_by_maintainer,
                       }

                writer.writerow(row)

    log.info('Calling R...')
    call(['./analyses/ignored_patches.R', config.d_R, config.f_characteristics, config.f_releases])


def prepare_off_list_patches(config, clustering):
    repo = config.repo
    # We need information of upstream commits, so warm up caches
    config.load_ccache_upstream()

    characteristics, maintainers_version = \
        load_characteristics_and_maintainers(config, clustering)

    offlist = set()
    for downstream, upstream in tqdm(clustering.iter_split()):
        # We're not interested in clusters with no upstream hash
        # Filter for patches with too many upstream commits. They're very
        # likely no off-list patches.
        l_upsteam = len(upstream)
        if l_upsteam == 0 or l_upsteam > 2:
            continue

        # Across downstream patches: drop all irrelevant patches
        downstream = {x for x in downstream if
                      not characteristics[x].is_from_bot and
                      not characteristics[x].is_next and
                      not characteristics[x].is_stable_review and
                      not characteristics[x].process_mail}

        # We don't have an offlist patch if anything is left in downstream
        if len(downstream):
            continue

        # Determine the youngest upstream commit (in most cases we only
        # have one upstream candidate in any case)
        upstream = get_first_upstream(repo, clustering, list(upstream)[0])
        offlist.add(upstream)

    csv_fields = ['commit',
                  'author',
                  'committer',
                  'subject',
                  'l_down',
                  'adate',
                  'cdate']
    with open(config.f_offlist, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()
        for o in sorted(offlist):
            patch = repo[o]
            writer.writerow({'commit': o,
                             'author': patch.author.email.lower(),
                             'committer': patch.committer.email.lower(),
                             'subject': patch.subject,
                             'l_down': len(clustering.get_downstream(o)),
                             'adate': format_date_ymd(patch.author.date),
                             'cdate': format_date_ymd(patch.committer.date)})


def prepare_patch_review(config, clustering):
    repo = config.repo
    threads = repo.mbox.load_threads()
    clusters = list(clustering.iter_split())

    clusters_responses = list()
    for cluster_id, (d, u) in enumerate(clusters):
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
                responses.append({'resp_msg_id': node.name,
                                  'parent': node.parent.name,
                                  'message': repo.mbox.get_raws(node.name)})

            clusters_responses.append({'cluster_id': cluster_id,
                                       'patch_id': patch_id,
                                       'upstream': u,
                                       'responses': responses})

    with open(config.f_responses_pkl, 'wb') as handle:
        pickle.dump(clusters_responses, handle, protocol=pickle.HIGHEST_PROTOCOL)
    log.info("Done writing response info for {} patch/commit entries!".format(len(clusters)))
    log.info("Total clusters found by pasta: {}".format(len(clusters)))


def prepare_evaluation(config, argv):
    parser = argparse.ArgumentParser(prog='prepare_evaluation',
                                     description='aggregate commit and patch info')

    parser.add_argument('--process_characteristics',
                        action='store_const',
                        const='process_characteristics',
                        dest='mode',
                        help='prepare data for process characteristics.\n'
                             'I.e., ignored and conform patch analysis \n'
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
        parser.error("No action requested, one of --process_characteristics, --off-list, or --review must be given")

    if config.mode != config.Mode.MBOX:
        log.error("Only works in Mbox mode!")
        return -1

    _, clustering = config.load_cluster()
    clustering.optimize()

    config.load_ccache_mbox()

    if analysis_option.mode == 'process_characteristics':
        prepare_process_characteristics(config, clustering)
    elif analysis_option.mode == 'off-list':
        prepare_off_list_patches(config, clustering)
    else:
        prepare_patch_review(config, clustering)

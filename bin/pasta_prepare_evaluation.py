"""
PaStA - Patch Stack Analysis

Copyright (c) Bayerische Motoren Werke Aktiengesellschaft (BMW AG), 2019
Copyright (c) OTH Regensburg, 2019-2021

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

from pypasta.MailCharacteristics import MailCharacteristics, PatchType

log = getLogger(__name__[-15:])

_repo = None
_config = None

MAIL_STRIP_TLD_REGEX = re.compile(r'(.*)\..+')


def prepare_process_characteristics(config, clustering):
    characteristics = load_characteristics(config, clustering)

    MailCharacteristics.dump_release_info(config)

    # These patches are relevant for the "ignored patches" analysis
    relevant_ignored = {mid for mid, c in characteristics.items() if
                        c.type == PatchType.PATCH}

    log.info('Identify ignored patches...')
    # Calculate ignored patches
    ignored_patches = {patch for patch in relevant_ignored if
                       not characteristics[patch].first_upstream and
                       not characteristics[patch].has_foreign_response}

    # Calculate ignored patches wrt to other patches in the cluster: A patch is
    # considered as ignored, if all related patches were ignored as well
    ignored_patches_related = \
        {patch for patch in ignored_patches if False not in
         [characteristics[x].has_foreign_response == False
          for x in (clustering.get_downstream(patch) & relevant_ignored)]}

    num_relevant = len(relevant_ignored)
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
                  'committer.xcorrect', # Is the committer a valid committer in the cluster of the maintainer?
    ]

    with open(config.f_characteristics, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
        writer.writeheader()

        for message_id in tqdm(sorted(clustering.get_downstream())):
            c = characteristics[message_id]
            mail_from = c.mail_from[1]

            ignored = None
            if message_id in relevant_ignored:
                ignored = message_id in ignored_target

            # Dump an entry for each list the patch was sent to. This allows
            # for grouping by mailing lists.
            for ml in sorted(c.lists):
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
                       'committer.correct': c.integrated_correct,
                       'committer.xcorrect': c.integrated_xcorrect,
                       }

                writer.writerow(row)

    log.info('Calling R...')
    call(['./analyses/ignored_patches.R', config.d_R, config.f_characteristics, config.f_releases])


def prepare_off_list_patches(config, clustering):
    repo = config.repo
    # We need information of upstream commits, so warm up caches
    config.load_ccache_upstream()

    characteristics = load_characteristics(config, clustering)

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

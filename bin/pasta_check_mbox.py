"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import sys

from fuzzywuzzy import fuzz
from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

log = getLogger(__name__[-15:])

repo = None

def shortlog(repo, hash, prefix=''):
    commit = repo[hash]
    log.info('%s%s: %s' % (prefix, hash, commit.subject))


def load_subject(message_id):
    # FIXME respect non-unique message ids
    message = repo.mbox.get_messages(message_id)[0]
    subject = message['Subject']
    if subject is None or not isinstance(subject, str):
        return None

    return message_id, subject


def check_mbox(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Check consistency of mailbox '
                                                 'result')

    parser.add_argument('-v', dest='verbose', default=False,
                        action='store_true', help='Also dump detected patches')
    parser.add_argument('-l', dest='lookup', default=False, action='store_true',
                        help='Perform a simple lookup')
    parser.add_argument('-rd', dest='respect_date', default=False,
                        action='store_true', help='Respect author date')
    parser.add_argument('range', type=str, nargs=1, help='Revision range')

    args = parser.parse_args(argv)

    if config.mode != config.Mode.MBOX:
        log.error('Only works in Mbox mode!')
        return -1

    global repo
    repo = config.repo
    _, cluster = config.load_patch_groups()

    range = repo.get_commithash_range(args.range[0])
    repo.cache_commits(range)

    found = []
    not_found = []

    log.info('Processing %s' % args.range[0])
    date_selector = get_date_selector(repo, None, 'AD')

    for commit_hash in range:
        commit = repo[commit_hash]

        # we can skip merge commits
        if commit.is_merge_commit:
            continue

        if commit_hash not in cluster:
            not_found.append(commit_hash)
            continue

        mails = cluster.get_untagged(commit_hash)
        if len(mails) == 0:
            not_found.append(commit_hash)
            continue

        if not args.respect_date:
            found.append(commit_hash)
            continue

        # We have to respect the author date in order to filter out backports.
        if PatchComposition.is_forwardport(repo, cluster, date_selector, commit_hash):
            found.append(commit_hash)
        else:
            not_found.append(commit_hash)

    if args.verbose:
        for detected in found:
            shortlog(repo, detected)
            for message_id in cluster.get_untagged(detected):
                shortlog(repo, message_id, '  -> ')

    log.info('Commit hashes with no mapped Message-Id:')
    for missing in not_found:
        shortlog(repo, missing)

    log.info('Stats: %d/%d clusters have at least one mail assigned' %
             (len(found), len(found) + len(not_found)))

    if not args.lookup:
        return 0

    message_ids = repo.mbox.message_ids(allow_invalid=True)
    valid_ids = repo.mbox.message_ids(allow_invalid=False)

    with Pool(cpu_count()) as p:
        result = tqdm(p.imap(load_subject, message_ids), total=len(message_ids))
        result = dict(filter(None, result))

    for missing in not_found:
        commit = repo[missing]
        original_subject = commit.subject.lower()
        printed = False

        for message_id, subject in result.items():
            subject = subject.lower()

            is_patch = '   PATCH' if message_id in valid_ids else 'NO PATCH'

            if fuzz.ratio(original_subject, subject) > 80:
                if not printed:
                    log.info('%s ("%s") might be...' %
                             (missing, commit.subject))
                    printed = True
                log.info('  -> (%s) %s ("%s")' %
                         (is_patch, message_id.ljust(55), subject))
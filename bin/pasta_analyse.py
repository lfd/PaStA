#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import re
import sys

from functools import partial
from logging import getLogger
from multiprocessing import cpu_count, Pool

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pypasta import *

log = getLogger(__name__[-15:])

_repo = None


def _evaluate_patch_list_wrapper(thresholds, args):
    global _repo
    orig, cand = args
    return evaluate_commit_list(_repo, thresholds,
                                False, EvaluationType.PatchStack,
                                orig, cand,
                                parallelise=False)


def find_cherries(repo, commit_hashes, dest_list):
    """
    find_cherries() takes a list of commit hashes, a list of potential
    candidates and the type of the evaluation (PatchStack / Upstream) and tries
    to detect if one commit is the cherry pick of another.

    Cherry picks can happen everywhere: picks across patch stacks, or picks from
    upstream. We have to distinguish between those types.

    :param repo: Repository
    :param commit_hashes: list of commit-hashes
    :param dest_list: list of potential cherry-pick hashes
    :return: EvaluationResult containing all detected cherry picks
    """
    log.info('Auto-detecting cherry-picks')
    cherries = EvaluationResult()

    cherry_rgxs = [r'.*pick.*', r'.*upstream.*commit.*',
                   r'.*commit.*upstream.*']
    cherry_rgxs = re.compile('(' + ')|('.join(cherry_rgxs) + ')', re.IGNORECASE)
    sha1_regex = re.compile(r'\b([0-9a-fA-F]{5,40})\b')

    for commit_hash in commit_hashes:
        commit = repo[commit_hash]
        for line in commit.message:
            if cherry_rgxs.match(line):
                sha_found = sha1_regex.search(line)
                if not sha_found:
                    continue

                cherry = sha_found.group(1)
                if cherry in dest_list:
                    if commit_hash in cherries:
                        cherries[commit_hash].append((cherry,
                                                      SimRating(1.0, 1.0, 1.0)))
                    else:
                        cherries[commit_hash] = [(cherry,
                                                  SimRating(1.0, 1.0, 1.0))]
                else:
                    log.info('Found cherry-pick %s <-> %s but it is not a '
                             'valid reference in this context'
                             % (commit_hash, cherry))

    log.info('  ↪ done. Found %d cherry-picks' % len(cherries))
    return cherries


def analyse(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Analyse patch stacks')

    # thresholds
    parser.add_argument('-th', dest='thres_heading', metavar='threshold',
                        default=config.thresholds.heading, type=float,
                        help='Minimum diff hunk section heading similarity '
                             '(default: %(default)s)')
    parser.add_argument('-tf', dest='thres_filename', metavar='threshold',
                        default=config.thresholds.filename, type=float,
                        help='Minimum filename similarity '
                             '(default: %(default)s)')
    parser.add_argument('-dlr', dest='thres_diff_lines', metavar='threshold',
                        type=float, default=config.thresholds.diff_lines_ratio,
                        help='Diff lines ratio threshold (default: %(default)s)')
    parser.add_argument('-adi', dest='thres_adi', metavar='days', type=int,
                        default=config.thresholds.author_date_interval,
                        help='Author date interval (default: %(default)s)')

    parser.add_argument('-er', dest='er_filename', metavar='filename',
                        default=config.f_evaluation_result,
                        help='Evaluation result PKL filename')

    parser.add_argument('-cpu', dest='cpu_factor', metavar='cpu', type=float,
                        default=1.0, help='CPU factor for parallelisation '
                                          '(default: %(default)s)')

    # choose analysis mode
    parser.add_argument('mode', default='succ',
                        choices=['succ', 'rep', 'upstream'],
                        help='rep: '
                             'compare representatives of the stack - '
                             'succ: '
                             'compare successive versions of the stacks - '
                             'upstream: '
                             'compare representatives against upstream - '
                             '(default: %(default)s)')

    parser.add_argument('-upstream', dest='upstream_range',
                        metavar='<revision range>', default=None,
                        help='Specify upstream revision range, '
                             'e.g.: v0.1..v0.2 (default: %s)' %
                             config.upstream_range)

    args = parser.parse_args(argv)

    config.thresholds.heading = args.thres_heading
    config.thresholds.filename = args.thres_filename
    config.thresholds.diff_lines_ratio = args.thres_diff_lines
    config.thresholds.author_date_interval = args.thres_adi

    repo = config.repo
    mbox = config.mode == Config.Mode.MBOX
    mode = args.mode

    f_patch_groups, patch_groups = config.load_patch_groups(must_exist=False)

    if mbox:
        mbox_time_window = config.mbox_mindate, config.mbox_maxdate
        log.info('Regarding mails in time window %s--%s' %
                 (format_date_ymd(mbox_time_window[0]),
                  format_date_ymd(mbox_time_window[1])))
        # load mbox ccache very early, because we need it in any case if it
        # exists.
        config.load_ccache_mbox()
        victims = config.repo.mbox.message_ids(mbox_time_window)

        # we have to temporarily cache those commits to filter out invalid
        # emails. Commit cache is already loaded, so evict everything except
        # victims and then cache all victims.
        repo.cache_evict_except(victims)
        repo.cache_commits(victims)

        # we might have loaded invalid emails, so reload the victim list once more.
        victims = config.repo.mbox.message_ids(mbox_time_window)
        print(len(victims))
    else:
        victims = config.psd.commits_on_stacks

    # insert victims
    for commit_hash in victims:
        patch_groups.insert_single(commit_hash)

    # intermediate persistence
    patch_groups.to_file(f_patch_groups)

    cherries = EvaluationResult()
    if mode == 'succ':
        if mbox:
            log.error('Analysis mode succ is not available in mailbox mode!')
            quit(-1)

        num_cpus = int(cpu_count() * args.cpu_factor)

        psd = config.psd
        global _repo
        repo = config.repo
        _repo = repo

        config.load_ccache_stack()

        evaluation_list = []
        for patch_stack in psd:
            successor = psd.get_successor(patch_stack)
            if successor == None:
                break

            log.info('Queueing %s <-> %s' % (patch_stack.stack_version,
                                             successor.stack_version))
            evaluation_list.append((patch_stack.commit_hashes,
                                    successor.commit_hashes))

        # cache missing commits
        repo.cache_commits(psd.commits_on_stacks)

        cherries = find_cherries(repo,
                                 psd.commits_on_stacks, psd.commits_on_stacks)

        f = partial(_evaluate_patch_list_wrapper, config.thresholds)
        log.info('Starting evaluation.')
        pool = Pool(num_cpus, maxtasksperchild=1)
        results = pool.map(f, evaluation_list, chunksize=5)
        pool.close()
        pool.join()
        log.info('  ↪ done.')
        _repo = None

        evaluation_result = EvaluationResult(False, EvaluationType.PatchStack)

        for result in results:
            evaluation_result.merge(result)

    else: # mode is rep or upstream
        # iterate over similar patch list and get latest commit of patches
        log.info('Determining patch stack representative system')

        # Get the complete representative system
        # The lambda compares two patches of an equivalence class and chooses
        # the one with the later release version
        if mbox:
            repo.cache_commits(patch_groups.get_untagged())
            representatives = patch_groups.get_representative_system(
                lambda x, y:
                    repo.get_commit(x).author_date >
                    repo.get_commit(y).author_date)
        else:
            representatives = patch_groups.get_representative_system(
                lambda x, y: config.psd.is_stack_version_greater(
                    config.psd.get_stack_of_commit(x),
                    config.psd.get_stack_of_commit(y)))
        log.info('  ↪ done')

        if mode == 'upstream':
            if args.upstream_range is not None:
                candidates = set(repo.get_commithash_range(args.upstream_range))
            else:
                candidates = set(config.upstream_hashes)

            config.load_ccache_upstream()

            # cache missing commits
            repo.cache_commits(representatives | candidates)
            repo.cache_evict_except(representatives | candidates)

            cherries = find_cherries(repo, representatives, candidates)
            type = EvaluationType.Upstream
        elif mode == 'rep':
            repo.cache_commits(representatives)
            candidates = representatives

            if not mbox:
                cherries = find_cherries(repo, representatives,
                                         config.psd.commits_on_stacks)

            type = EvaluationType.PatchStack

        log.info('Starting evaluation')
        evaluation_result = evaluate_commit_list(repo, config.thresholds,
                                                 mbox, type,
                                                 representatives, candidates,
                                                 parallelise=True, verbose=True,
                                                 cpu_factor=args.cpu_factor)
        log.info('  ↪ done.')

    evaluation_result.merge(cherries)
    evaluation_result.to_file(args.er_filename)


if __name__ == '__main__':
    config = Config(sys.argv[1])
    analyse(config, sys.argv[0], sys.argv[2:])

#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import copy
import os
import re
import sys

from functools import partial
from multiprocessing import cpu_count, Pool
from termcolor import colored

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *

from PaStA.PatchEvaluation import FalsePositives


_repo = None


def _evaluate_patch_list_wrapper(type, thresholds, args):
    global _repo
    orig, cand = args
    return evaluate_commit_list(_repo, thresholds,
                                orig, cand,
                                type,
                                parallelise=False)


def find_cherries(repo, commit_hashes, dest_list, type):
    """
    find_cherries() takes a list of commit hashes, a list of potential
    candidates and the type of the evaluation (PatchStack / Upstream) and tries
    to detect if one commit is the cherry pick of another.

    Cherry picks can happen everywhere: picks across patch stacks, or picks from
    upstream. We have to distinguish between those types.

    :param repo: Repository
    :param commit_hashes: list of commit-hashes
    :param dest_list: list of potential cherry-pick hashes
    :param type: PatchStack or Upstream
    :return: EvaluationResult containing all detected cherry picks
    """
    print('Auto-detecting cherry-picks...')
    cherries = EvaluationResult(type)
    cherries.set_universe(set())

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
                    print('Found cherry-pick: %s <-> %s but it is not a valid '
                          'reference in this context' % (commit_hash, cherry))

    print('Done. Found %d cherry-picks' % len(cherries))
    return cherries


def analyse_succ(config):
    cpu_factor = 1.0
    num_cpus = int(cpu_count() * cpu_factor)

    # analyse_succ: compare successive stacks
    psd = config.psd
    global _repo
    repo = config.repo
    _repo = repo
    repo.load_ccache(config.f_ccache_stack)

    evaluation_list = []
    for patch_stack in psd:
        successor = psd.get_successor(patch_stack)
        if successor == None:
            break

        print('Queueing %s <-> %s' % (patch_stack.stack_version,
                                      successor.stack_version))
        evaluation_list.append((patch_stack.commit_hashes,
                                successor.commit_hashes))

    # cache missing commits
    repo.cache_commits(psd.commits_on_stacks)

    cherries = find_cherries(repo,
                             psd.commits_on_stacks,
                             psd.commits_on_stacks,
                             EvaluationType.PatchStack)

    f = partial(_evaluate_patch_list_wrapper, EvaluationType.PatchStack,
                config.thresholds)
    print('Starting evaluation.')
    pool = Pool(num_cpus, maxtasksperchild=1)
    results = pool.map(f, evaluation_list, chunksize=5)
    pool.close()
    pool.join()
    print('Evaluation completed.')
    _repo = None

    evaluation_result = EvaluationResult(EvaluationType.PatchStack)
    evaluation_result.set_universe(psd.commits_on_stacks)
    for result in results:
        evaluation_result.merge(result)
    evaluation_result.merge(cherries)

    return evaluation_result


def analyse_stack(config, similar_patches):
    psd = config.psd
    repo = config.repo

    # Iterate over similar patch list and get latest commit of patches
    sys.stdout.write('Determining patch stack representative system...')
    sys.stdout.flush()
    # Get the complete representative system
    # The lambda compares two patches of an equivalence class and chooses the
    # one with the later release version
    representatives = similar_patches.get_representative_system(
        lambda x, y: psd.is_stack_version_greater(psd.get_stack_of_commit(x),
                                                  psd.get_stack_of_commit(y)))
    print(colored(' [done]', 'green'))

    # cache commits
    repo.cache_commits(representatives)

    cherries = find_cherries(repo,
                             representatives,
                             psd.commits_on_stacks,
                             EvaluationType.PatchStack)

    print('Starting evaluation.')
    evaluation_result = evaluate_commit_list(repo, config.thresholds,
                                             representatives, representatives,
                                             EvaluationType.PatchStack,
                                             parallelise=True, verbose=True)
    print('Evaluation completed.')
    evaluation_result.merge(cherries)
    evaluation_result.set_universe(representatives)

    return evaluation_result


def analyse_upstream(config, similar_patches):
    repo = config.repo
    psd = config.psd

    repo.load_ccache(config.f_ccache_upstream, must_exist=False)

    sys.stdout.write('Determining patch stack representative system...')
    sys.stdout.flush()
    # Get the complete representative system
    # The lambda compares two patches of an equivalence class and chooses the
    # one with the later release version
    representatives = similar_patches.get_representative_system(
        lambda x, y: psd.is_stack_version_greater(psd.get_stack_of_commit(x),
                                                  psd.get_stack_of_commit(y)))
    print(colored(' [done]', 'green'))

    # cache missing commits
    repo.cache_commits(psd.upstream_hashes)
    repo.cache_commits(representatives)

    cherries = find_cherries(repo,
                             representatives,
                             psd.upstream_hashes,
                             EvaluationType.Upstream)

    print('Starting evaluation.')
    evaluation_result = evaluate_commit_list(repo, config.thresholds,
                                             representatives,
                                             psd.upstream_hashes,
                                             EvaluationType.Upstream,
                                             parallelise=True, verbose=True,
                                             cpu_factor=0.25)
    print('Evaluation completed.')

    evaluation_result.merge(cherries)

    # We don't have a universe in this case
    evaluation_result.set_universe(set())

    return evaluation_result


def analyse_mbox(config, mindate, maxdate):
    config.fail_no_mailbox()

    upstream_hashes = set(config.psd.upstream_hashes)
    repo = config.repo

    repo.load_ccache(config.f_ccache_mbox)
    repo.load_ccache(config.f_ccache_upstream)

    message_ids = repo.mbox_get_message_ids(mindate, maxdate)

    repo.cache_commits(upstream_hashes)
    message_ids, _ = repo.cache_commits(message_ids)

    repo.cache_evict_except(upstream_hashes | message_ids)

    print('Starting evaluation.')
    evaluation_result = evaluate_commit_list(config.repo, config.thresholds,
                                             message_ids, upstream_hashes,
                                             EvaluationType.Mailinglist,
                                             parallelise=True, verbose=True)
    print('Evaluation completed.')
    return evaluation_result


def create_patch_groups(config):
    # similar patches on patch stacks
    similar_patches = EquivalenceClass.from_file(config.f_similar_patches,
                                                 must_exist=True)

    # similar representatives -> upstream
    similar_upstream = EquivalenceClass.from_file(config.f_similar_upstream,
                                                  must_exist=True)

    # perform some consistency checks before creating the patch groups
    for i in similar_upstream:
        if len(i) != 1:
            print('Consistency error in similar_upstream file: '
                  'Multiple patches are mapped to the same upstream: %s' % i)
            quit()

    # load false positives
    fp_ps = FalsePositives(EvaluationType.PatchStack, config.d_false_positives)
    fp_su = FalsePositives(EvaluationType.Upstream, config.d_false_positives)

    # check consistency of false positives
    fp_ps.check_consistency(similar_patches)
    fp_su.check_consistency(similar_upstream)

    # create a copy of the similar patch list
    patch_groups = copy.deepcopy(similar_patches)

    # Insert every single key of the patch stack into the transitive list.
    # Already existing keys will be skipped. This results in a list with at
    # least one key for each patch set
    stack_commit_hashes = config.psd.commits_on_stacks
    for i in stack_commit_hashes:
        patch_groups.insert_single(i)
    patch_groups.optimize()

    # Merge upstream results and patch group list
    for i in similar_upstream:
        up = patch_groups.get_property(i[0])
        if up is not None:
            print('Error: Patch group %s already mapped to upstream patch %s' %
                  (i[0], up))
            print('Unable to overwrite with %s. Exiting.' % i.property)
            quit()
        patch_groups.set_property(i[0], i.property)

    sys.stdout.write('Writing Patch Group file... ')
    patch_groups.to_file(config.f_patch_groups)
    print(colored(' [done]', 'green'))


def analyse(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog,
                                     description='Analyse patch stacks')

    # Thresholds
    parser.add_argument('-th', dest='thres_heading', metavar='threshold',
                        default=config.thresholds.heading, type=float,
                        help='Minimum diff hunk section heading similarity '
                             '(default: %(default)s)')
    parser.add_argument('-tf', dest='thres_filename', metavar='threshold',
                        default=config.thresholds.filename, type=float,
                        help='Minimum filename similarity '
                             '(default: %(default)s)')

    parser.add_argument('mode', default='stack-succ',
                        choices=['init', 'stack-succ', 'stack-rep', 'upstream',
                                 'finish', 'mbox'],
                        help='init: initialise\n'
                             'stack-rep: '
                             'compare representatives of the stack - '
                             'stack-succ: '
                             'compare successive versions of the stacks - '
                             'upstream: '
                             'compare representatives against upstream - '
                             'finish: '
                             'create patch-groups file - '
                             'mbox: '
                             'do mailbox analysis against upstream '
                             '(default: %(default)s)')

    parser.add_argument('-mindate', dest='mindate', metavar='mindate',
                        default=config.mbox_mindate, type=parse_date_ymd,
                        help='Skip mails older than mindate '
                             '(only together with  mbox, default: %(default)s)')
    parser.add_argument('-maxdate', dest='maxdate', metavar='maxdate',
                        default=config.mbox_maxdate, type=parse_date_ymd,
                        help='Skip mails older than mindate '
                             '(only together with mbox, default: %(default)s)')

    args = parser.parse_args(argv)

    config.thresholds.heading = args.thres_heading
    config.thresholds.filename = args.thres_filename

    # Load similar patches file. If args.mode is 'init' or 'mbox', it does not
    # necessarily have to exist.
    sp_must_exist = args.mode not in ['init', 'mbox']
    similar_patches = EquivalenceClass.from_file(config.f_similar_patches,
                                                 must_exist=sp_must_exist)

    if args.mode == 'init':
        for commit_hash in config.psd.commits_on_stacks:
            similar_patches.insert_single(commit_hash)
        similar_patches.to_file(config.f_similar_patches)
    elif args.mode == 'finish':
        create_patch_groups(config)
    else:
        if args.mode == 'stack-succ':
            result = analyse_succ(config)
        elif args.mode == 'stack-rep':
            result = analyse_stack(config, similar_patches)
        elif args.mode == 'upstream':
            result = analyse_upstream(config, similar_patches)
        elif args.mode == 'mbox':
            result = analyse_mbox(config, args.mindate, args.maxdate)

        result.to_file(config.f_evaluation_result)


if __name__ == '__main__':
    config = Config(sys.argv[1])
    analyse(config, sys.argv[0], sys.argv[2:])

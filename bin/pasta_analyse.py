#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import argparse
import copy
import os
import re
import sys

from multiprocessing import cpu_count, Pool
from termcolor import colored

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *


def _evaluate_patch_list_wrapper(args):
    orig, cand, type = args
    return evaluate_commit_list(orig, cand, type, config.thresholds)


def find_cherries(commit_hashes, dest_list, type):
    """
    find_cherries() takes a list of commit hashes, a list of potential candidates and
    the type of the evaluation (PatchStack / Upstream).

    A cherry pick can happen on both sides: Pick from one patch stacks to another one or
    a pick from upstream. We have to distinguish between those types.
    :param commit_hashes: list of commit-hashes
    :param dest_list: list of potential cherry-pick hashes
    :param type: PatchStack or Upstream
    :return: EvaluationResult containing all detected cherry picks
    """
    print('Auto-detecting cherry-picks...')
    cherries = EvaluationResult(type)
    cherries.set_universe(set())

    cherry_rgxs = [r'.*pick.*',
                   r'.*upstream.*commit.*',
                   r'.*commit.*upstream.*']
    cherry_rgxs = re.compile('(' + ')|('.join(cherry_rgxs) + ')', re.IGNORECASE)
    sha1_regex = re.compile(r'\b([0-9a-fA-F]{5,40})\b')

    for commit_hash in commit_hashes:
        commit = get_commit(commit_hash)
        for line in commit.message:
            if cherry_rgxs.match(line):
                sha_found = sha1_regex.search(line)
                if not sha_found:
                    continue

                cherry = sha_found.group(1)
                if cherry in dest_list:
                    if commit_hash in cherries:
                        cherries[commit_hash].append((cherry, SimRating(1.0, 1.0, 1.0)))
                    else:
                        cherries[commit_hash] = [(cherry, SimRating(1.0, 1.0, 1.0))]
                else:
                    print('Found cherry-pick: %s <-> %s but it is not a valid reference in this context' %
                          (commit_hash, cherry))

    print('Done. Found %d cherry-picks' % len(cherries))
    return cherries


def analyse_succ():
    # Check stacks against successive stacks
    evaluation_list = []
    for patch_stack in patch_stack_definition:
        successor = patch_stack_definition.get_successor(patch_stack)
        if successor == None:
            break

        print('Queueing %s <-> %s' % (patch_stack.stack_version, successor.stack_version))
        evaluation_list.append((patch_stack.commit_hashes, successor.commit_hashes, EvaluationType.PatchStack))

    cache_commits(patch_stack_definition.commits_on_stacks)

    cherries = find_cherries(patch_stack_definition.commits_on_stacks,
                             patch_stack_definition.commits_on_stacks,
                             EvaluationType.PatchStack)

    print('Starting evaluation.')
    pool = Pool(cpu_count())
    results = pool.map(_evaluate_patch_list_wrapper, evaluation_list, chunksize=1)
    pool.close()
    pool.join()
    print('Evaluation completed.')

    evaluation_result = EvaluationResult(EvaluationType.PatchStack)
    evaluation_result.set_universe(patch_stack_definition.commits_on_stacks)
    for result in results:
        evaluation_result.merge(result)
    evaluation_result.merge(cherries)

    return evaluation_result


def analyse_stack(similar_patches):

    # Iterate over similar patch list and get latest commit of patches
    sys.stdout.write('Determining patch stack representative system...')
    sys.stdout.flush()
    # Get the complete representative system
    # The lambda compares two patches of an equivalence class and chooses the one with
    # the later release version
    representatives = similar_patches.get_representative_system(
        lambda x, y: patch_stack_definition.is_stack_version_greater(patch_stack_definition.get_stack_of_commit(x),
                                                                     patch_stack_definition.get_stack_of_commit(y)))
    print(colored(' [done]', 'green'))

    # Cache commits
    cache_commits(representatives)

    cherries = find_cherries(representatives,
                             patch_stack_definition.commits_on_stacks,
                             EvaluationType.PatchStack)

    evaluation_result = evaluate_commit_list(representatives,
                                             representatives,
                                             EvaluationType.PatchStack,
                                             config.thresholds,
                                             parallelise=True,
                                             verbose=True)
    evaluation_result.merge(cherries)
    evaluation_result.set_universe(representatives)

    return evaluation_result


def analyse_upstream(similar_patches):
    sys.stdout.write('Determining patch stack representative system...')
    sys.stdout.flush()
    # Get the complete representative system
    # The lambda compares two patches of an equivalence class and chooses the one with
    # the later release version
    representatives = similar_patches.get_representative_system(
        lambda x, y: patch_stack_definition.is_stack_version_greater(patch_stack_definition.get_stack_of_commit(x),
                                                                     patch_stack_definition.get_stack_of_commit(y)))
    print(colored(' [done]', 'green'))

    cache_commits(patch_stack_definition.upstream_hashes)
    cache_commits(representatives)

    cherries = find_cherries(representatives,
                             patch_stack_definition.upstream_hashes,
                             EvaluationType.Upstream)

    print('Starting evaluation.')
    evaluation_result = evaluate_commit_list(representatives, patch_stack_definition.upstream_hashes,
                                             EvaluationType.Upstream, config.thresholds,
                                             parallelise=True, verbose=True,
                                             cpu_factor=0.5)
    print('Evaluation completed.')

    evaluation_result.merge(cherries)

    # We don't have a universe in this case
    evaluation_result.set_universe(set())

    return evaluation_result


def create_patch_groups(sp_filename, su_filename, pg_filename):
    # similar patch groups
    similar_patches = EquivalenceClass.from_file(sp_filename, must_exist=True)

    # upstream results
    similar_upstream = EquivalenceClass.from_file(su_filename, must_exist=True)

    # create a copy of the similar patch list
    patch_groups = copy.deepcopy(similar_patches)

    # Insert every single key of the patch stack into the transitive list. Already existing keys will be skipped.
    # This results in a list with at least one key for each patch set
    stack_commit_hashes = patch_stack_definition.commits_on_stacks
    for i in stack_commit_hashes:
        patch_groups.insert_single(i)
    patch_groups.optimize()

    # Merge upstream results and patch group list
    for i in similar_upstream:
        patch_groups.set_property(i[0], i.property)

    sys.stdout.write('Writing Patch Group file... ')
    patch_groups.to_file(pg_filename)
    print(colored(' [done]', 'green'))


def analyse(prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Analyse patch stacks')
    parser.add_argument('-er', dest='evaluation_result_filename', metavar='filename',
                        default=config.evaluation_result, help='Evaluation result filename')
    parser.add_argument('-sp', dest='sp_filename', metavar='filename',
                        default=config.similar_patches, help='Similar Patches filename')
    parser.add_argument('-su', dest='su_filename', metavar='filename',
                        default=config.similar_upstream,
                        help='Similar Upstream filename. Only required together with mode finish')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=config.patch_groups,
                        help='Patch groups filename. Only required with -mode finish')

    # Thresholds
    parser.add_argument('-th', dest='thres_heading', metavar='threshold', default=config.thresholds.heading, type=float,
                        help='Minimum diff hunk section heading similarity (default: %(default)s)')

    parser.add_argument('mode', default='stack-succ',
                        choices=['init', 'stack-succ', 'stack-rep', 'upstream', 'finish'],
                        help='init: initialise\n'
                             'stack-rep: compare representatives of the stack - '
                             'stack-succ: compare successive versions of the stacks - '
                             'upstream: compare representatives against upstream - '
                             'finish: create patch-groups file'
                             '(default: %(default)s)' )
    args = parser.parse_args(argv)

    config.thresholds.heading = args.thres_heading

    # Load similar patches file. If args.mode is 'init', it does not necessarily have to exist.
    sp_must_exist = args.mode != 'init'
    similar_patches = EquivalenceClass.from_file(args.sp_filename, must_exist=sp_must_exist)

    if args.mode == 'init':
        for commit_hash in patch_stack_definition.commits_on_stacks:
            similar_patches.insert_single(commit_hash)
        similar_patches.to_file(args.sp_filename)
    elif args.mode == 'finish':
        create_patch_groups(args.sp_filename, args.su_filename, args.pg_filename)
    else:
        if args.mode == 'stack-succ':
            result = analyse_succ()
        elif args.mode == 'stack-rep':
            result = analyse_stack(similar_patches)
        elif args.mode == 'upstream':
            result = analyse_upstream(similar_patches)

        result.to_file(args.evaluation_result_filename)


if __name__ == '__main__':
    analyse(sys.argv[0], sys.argv[1:])

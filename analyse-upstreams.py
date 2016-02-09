#!/usr/bin/env python3

import argparse
from git import Repo
from multiprocessing import Pool, cpu_count
import sys
from termcolor import colored

import blacklist
from PatchEvaluation import evaluate_patch_list
from PatchStack import KernelVersion, cache_commit_hashes, parse_patch_stack_definition, get_commit_hashes, get_commit
from Tools import EvaluationResult, TransitiveKeyList

REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'
EVALUATION_RESULT_FILENAME = './evaluation-result'
SIMILAR_PATCHES_FILE = './similar_patch_list'


def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand)

# Startup
parser = argparse.ArgumentParser(description='Analyse stack by stack')
parser.add_argument('-sd', dest='stack_def_filename', default=PATCH_STACK_DEFINITION, help='Stack definition filename')
parser.add_argument('-r', dest='repo_location', default=REPO_LOCATION, help='Repo location')
parser.add_argument('-er', dest='evaluation_result_filename', default=EVALUATION_RESULT_FILENAME, help='Evaluation result filename')
parser.add_argument('-sp', dest='sp_filename', default=SIMILAR_PATCHES_FILE, help='Similar Patches filename')

args = parser.parse_args()

# Load patch stack definition
repo = Repo(args.repo_location)
patch_stack_list = parse_patch_stack_definition(repo, args.stack_def_filename)

# Load and cache upstream commits
upstream_candidates = set(get_commit_hashes(repo, 'v3.0', 'master'))
upstream_candidates -= blacklist.linux_upstream_blacklist

# Load similar patches file
similar_patches = TransitiveKeyList.from_file(args.sp_filename)

candidates = []
for cur_patch_stack in patch_stack_list:

    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    #if cur_patch_stack.patch_version > KernelVersion('3.1'):
    #    break
    candidates += cur_patch_stack.commit_hashes

candidates = set(candidates)
cache_commit_hashes(candidates, parallelize=True)
cache_commit_hashes(upstream_candidates, parallelize=True)

# Iterate over similar patch list and get latest commit of patches
sys.stdout.write('Determining representatives...')
sys.stdout.flush()
representatives = set()
for similars in similar_patches:
    # Get latest patch in similars

    foo = list(map(lambda x: (x, get_commit(x).author_date), similars))
    foo.sort(key=lambda x: x[1]) # Checken, ob sortierung so stimmt

    representatives.add(foo[-1][0])

print(colored(' [done]', 'green'))
stack_candidates = (candidates - similar_patches.get_commit_hashes()) | representatives

evaluation_list = []
for i in stack_candidates:
    evaluation_list.append(([i], upstream_candidates))

print('Starting evaluation.')
pool = Pool(cpu_count())
results = pool.map(_evaluate_patch_list_wrapper, evaluation_list)
pool.close()
pool.join()
print('Evaluation completed.')

evaluation_result = EvaluationResult()
for result in results:
    evaluation_result.merge(result)

evaluation_result.to_file(args.evaluation_result_filename)

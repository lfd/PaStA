#!/usr/bin/env python3

import argparse
from git import Repo
from termcolor import colored

from config import *
from PatchEvaluation import evaluate_patch_list
from PatchStack import cache_commit_hashes, parse_patch_stack_definition, get_commit_hashes, get_commit
from Tools import TransitiveKeyList

EVALUATION_RESULT_FILENAME = './evaluation-result.pkl'


def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand)

# Startup
parser = argparse.ArgumentParser(description='Analyse stack by stack')
parser.add_argument('-er', dest='evaluation_result_filename', default=EVALUATION_RESULT_FILENAME, help='Evaluation result filename')
parser.add_argument('-sp', dest='sp_filename', default=SIMILAR_PATCHES_FILE, help='Similar Patches filename')

args = parser.parse_args()

# Load patch stack definition
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

# Load and cache upstream commits
upstream_candidates = set(get_commit_hashes(repo, UPSTREAM_MIN, UPSTREAM_MAX))
upstream_candidates -= COMMITHASH_BLACKLIST

# Load similar patches file
similar_patches = TransitiveKeyList.from_file(args.sp_filename)

candidates = set(patch_stack_list.get_all_commit_hashes())
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
stack_candidates = (candidates - similar_patches.get_all_commit_hashes()) | representatives

print('Starting evaluation.')
evaluation_result = evaluate_patch_list(stack_candidates, upstream_candidates,
                                        parallelize=True, verbose=True,
                                        cpu_factor = 0.5)
print('Evaluation completed.')

evaluation_result.to_file(args.evaluation_result_filename)

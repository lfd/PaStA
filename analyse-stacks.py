#!/usr/bin/env python3

import argparse
from git import Repo

from termcolor import colored

from EquivalenceClass import EquivalenceClass
from config import *
from PatchEvaluation import evaluate_patch_list
from PatchStack import cache_commit_hashes, parse_patch_stack_definition

EVALUATION_RESULT_FILENAME = './evaluation-result.pkl'


def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand)

# Startup
parser = argparse.ArgumentParser(description='Analyse stack by stack')
parser.add_argument('-er', dest='evaluation_result_filename', default=EVALUATION_RESULT_FILENAME, help='Evaluation result filename')
parser.add_argument('-sp', dest='sp_filename', default=SIMILAR_PATCHES_FILE, help='Similar Patches filename')

args = parser.parse_args()

repo = Repo(REPO_LOCATION)

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(PATCH_STACK_DEFINITION)

# Load similar patches file
similar_patches = EquivalenceClass.from_file(args.sp_filename)

# Iterate over similar patch list and get latest commit of patches
sys.stdout.write('Determining patch stack representative system...')
sys.stdout.flush()
# Get the complete representative system
# The lambda compares two patches of an equivalence class and chooses the one with
# the later release version
representatives = similar_patches.get_representative_system(
    lambda x, y: patch_stack_list.is_stack_version_greater(patch_stack_list.get_stack_of_commit(x),
                                                           patch_stack_list.get_stack_of_commit(y)))

print(colored(' [done]', 'green'))

# Cache commits
cache_commit_hashes(representatives)

evaluation_result = evaluate_patch_list(representatives,
                                        representatives,
                                        parallelize=True,
                                        verbose=True)
evaluation_result.set_universe(representatives)
evaluation_result.to_file(args.evaluation_result_filename)

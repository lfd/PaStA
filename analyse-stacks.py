#!/usr/bin/env python3

from git import Repo
from multiprocessing import Pool, cpu_count

from PatchEvaluation import evaluate_patch_list, merge_evaluation_results, interactive_rating
from PatchStack import KernelVersion, cache_commit_hashes, parse_patch_stack_definition, get_commit_hashes
from Tools import DictList, TransitiveKeyList

REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'
SIMILAR_PATCHES_FILE = './similar_patch_list'
FALSE_POSTITIVES_FILES = './false-positives'

INTERACTIVE_THRESHOLD = 350
AUTOACCEPT_THRESHOLD = 400

def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand,
                               verbose=True)

# Startup
repo = Repo(REPO_LOCATION)

# Load already known positives and false positives
similar_patches = TransitiveKeyList.from_file(SIMILAR_PATCHES_FILE)
false_positives = DictList.from_file(FALSE_POSTITIVES_FILES, human_readable=False)

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

# Check patch against all other patches
evaluation_result = {}
evaluation_list = []
candidates = []

for cur_patch_stack in patch_stack_list:

    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    #if cur_patch_stack.patch_version > KernelVersion('3.1'):
    #    break
    candidates += cur_patch_stack.commit_hashes

cache_commit_hashes(candidates)
for cur_patch_stack in patch_stack_list:
    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    if cur_patch_stack.patch_version > KernelVersion('3.1'):
        break

    print('Queueing ' + str(cur_patch_stack.patch_version) + ' <-> All others')

    print('Starting evaluation.')
    result = evaluate_patch_list(cur_patch_stack.commit_hashes, candidates,
                                 parallelize=True, verbose=True)
    print('Evaluation completed.')
    print('Prefiltering results to save memory.')
    for orig_commit_hash, list_of_candidates in result.items():
        result[orig_commit_hash] = list(filter(lambda x: x[1] > INTERACTIVE_THRESHOLD, list_of_candidates))

    foo = sum(map(lambda x: len(x[1]), result.items()))
    print('FYI: ' + str(foo) + ' items!')

    merge_evaluation_results(evaluation_result, result)

    # Save memory
    result = None


interactive_rating(similar_patches, false_positives, evaluation_result,
                   AUTOACCEPT_THRESHOLD, INTERACTIVE_THRESHOLD)

similar_patches.to_file(SIMILAR_PATCHES_FILE)
false_positives.to_file(FALSE_POSTITIVES_FILES, human_readable=False)
false_positives.to_file(FALSE_POSTITIVES_FILES, human_readable=True)

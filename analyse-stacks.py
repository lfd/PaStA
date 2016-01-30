#!/usr/bin/env python3

from git import Repo
from multiprocessing import Pool, cpu_count

from PatchEvaluation import evaluate_patch_list, merge_evaluation_results, interactive_rating
from PatchStack import KernelVersion, cache_commit_hashes, parse_patch_stack_definition
from Tools import DictList, TransitiveKeyList

REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'
SIMILAR_PATCHES_FILE = './similar_patch_list'
FALSE_POSTITIVES_FILES = './false-positives'

INTERACTIVE_THRESHOLD = 350
AUTOACCEPT_THRESHOLD = 400

def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand)

# Startup
repo = Repo(REPO_LOCATION)

# Load already known positives and false positives
similar_patches = TransitiveKeyList.from_file(SIMILAR_PATCHES_FILE)
false_positives = DictList.from_file(FALSE_POSTITIVES_FILES, human_readable=False)

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

# Check patch against next patch version number, patch by patch
evaluation_result = {}
evaluation_list = []
for index, cur_patch_stack in enumerate(patch_stack_list):

    # Bounds check
    if index == len(patch_stack_list)-1:
        break

    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    #if cur_patch_stack.patch_version > KernelVersion('3.1'):
    #    break

    next_patch_stack = patch_stack_list[index + 1]
    print('Queueing ' + str(cur_patch_stack.patch_version) + ' <-> ' + str(next_patch_stack.patch_version))

    cache_commit_hashes(cur_patch_stack.commit_hashes)
    cache_commit_hashes(next_patch_stack.commit_hashes)
    print('')

    evaluation_list.append((cur_patch_stack.commit_hashes, next_patch_stack.commit_hashes))

print('Starting evaluation.')

pool = Pool(cpu_count())
results = pool.map(_evaluate_patch_list_wrapper, evaluation_list)
pool.close()
pool.join()

print('Evaluation completed.')

for result in results:
    merge_evaluation_results(evaluation_result, result)

interactive_rating(similar_patches, false_positives, evaluation_result,
                   AUTOACCEPT_THRESHOLD, INTERACTIVE_THRESHOLD)

similar_patches.to_file(SIMILAR_PATCHES_FILE)
false_positives.to_file(FALSE_POSTITIVES_FILES, human_readable=False)
false_positives.to_file(FALSE_POSTITIVES_FILES, human_readable=True)

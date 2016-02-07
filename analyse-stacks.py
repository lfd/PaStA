#!/usr/bin/env python3

from git import Repo
from multiprocessing import Pool, cpu_count

from PatchEvaluation import evaluate_patch_list
from PatchStack import KernelVersion, cache_commit_hashes, parse_patch_stack_definition, get_commit_hashes
from Tools import DictList, EvaluationResult, TransitiveKeyList

REPO_LOCATION = './linux/'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'

def _evaluate_patch_list_wrapper(args):
    orig, cand = args
    return evaluate_patch_list(orig, cand)

# Startup
repo = Repo(REPO_LOCATION)

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

# Check patch against all other patches
evaluation_result = EvaluationResult()
evaluation_list = []
candidates = []

for cur_patch_stack in patch_stack_list:

    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    #if cur_patch_stack.patch_version > KernelVersion('3.1'):
    #    break
    candidates += cur_patch_stack.commit_hashes

cache_commit_hashes(candidates, parallelize=True)

for cur_patch_stack in patch_stack_list:
    # Skip till version 3.0
    if cur_patch_stack.patch_version < KernelVersion('2.6.999'):
        continue
    if cur_patch_stack.patch_version > KernelVersion('3.1'):
        break

    print('Queueing ' + str(cur_patch_stack.patch_version) + ' <-> All others')
    evaluation_list.append((cur_patch_stack.commit_hashes, candidates))


print('Starting evaluation.')
pool = Pool(cpu_count())
results = pool.map(_evaluate_patch_list_wrapper, evaluation_list)
pool.close()
pool.join()
print('Evaluation completed.')

for result in results:
    evaluation_result.merge(result)

evaluation_result.to_file('foofile')

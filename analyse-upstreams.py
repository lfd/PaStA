#!/usr/bin/env python3

import argparse
from git import Repo
from multiprocessing import Pool, cpu_count
import sys
from termcolor import colored

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

repo = Repo(args.repo_location)
upstream_candidates = set(get_commit_hashes(repo, 'v3.0', 'master'))
upstream_candidates = upstream_candidates - set(['007c33bb9c8ee4ca7a7f0003a4529ad7df0c9e5c',
                                                '06d96c0ff77f20dbf5fc93c8cfa9a2a9690fd67e',
                                                '09792200e465db0861dee25bdecfc55278907ed3',
                                                '0a4dfa28f403f47a5aeb68394541fa1866de4922',
                                                '0da1fa0aa2b438aaee6764742d45766d6a9283bc',
                                                '0ea6e61122196509af82cc4f36cbdaacbefb8227',
                                                '0ea6e61122196509af82cc4f36cbdaacbefb8227',
                                                '12428e7626378dec7968cd4f5df9aab2ee58e735',
                                                '1980a347a71693a41663a1780c2da869174a0025',
                                                '22033d38bca82a4a511450562086c69f5dc457ee',
                                                '2249aa5c97a017be4e3b5bb0e9a3ca2d2ed31b27',
                                                '24277db3894941026662743e400e77c68c4a9e92',
                                                '25eb650a690b95cb0e2cf0c3b03f4900a59e0135',
                                                '27b18dd97ef23b8f4838fdb3a619e6fd369f87e9',
                                                '29a68ee73ec6a5510cbf9d803cbf6190b615e276',
                                                '2f05543029a2efaa19845a73f79b7330142d11e8',
                                                '3396c7823efb3a5b8630388c464e1034ea031ced',
                                                '37c703f40dd8b35095f7f8d564bc57afa9a42e5f',
                                                '390b421c42c8b749661f018818f1d34f339fc3b2',
                                                '3ccff540070b5adde7eec443676cfee1dd6b89fd',
                                                '463e526083fdaa284eaea45b53bb917ed3c72900',
                                                '48d9854285635dd8b0535af7cb0d508b08db9e98',
                                                '4997166a393851d0595f85cbe1195208d582e172',
                                                '4bdac7b668d29dcaa53b72921b7f6a51d0f80b9b',
                                                '5dae82cc186da487cf33d7f5648a9ab3e02eaee4',
                                                '63a29f744fe1c19742039ce7526663a98f172f7e',
                                                '6941ee8896bfc462c3e3ad113c769a57ecbf3b2a',
                                                '6b2cb91efce215c3c34b1b79b15f30e860761a3e',
                                                '6d6a49e9c9dddff61649249c2b0d5d462fa1a692',
                                                '6e2187bf59a1452ed26a2f3baf6e4900c62fcd6c',
                                                '7aca5a7f4911044b45c1b35defb4f7f225dd5686',
                                                '83ca897d170919035acfe5c472479941847e93cc',
                                                '89098bfcf5944e4aab98c83de3cf4c0d802e8d3f',
                                                '8db0f9343a2a9e965257de159a140cf995f113fb',
                                                '9194a595f756d2e428ddb8e74eb4932d39963aad',
                                                '98b0f811aade1b7c6e7806c86aa0befd5919d65f',
                                                'a15112eb604795fcb24ad19a7de9c7a8ee621120',
                                                'a2531293dbb7608fa672ff28efe3ab4027917a2f',
                                                'a786a7c0ad44985548118fd2370c792c0da36891',
                                                'a9e73211fb0fc875637793a8af770f3678b6c278',
                                                'ab22e77cd3d3073c8cac51b59713ef635678dfbe',
                                                'b0ab8a9030b655e02c5532d1f78b9ba9d9ff4420',
                                                'b5416d32a6f1a4cd4e399654b4bac7f558ab237e',
                                                'b5ced6b3653afc7bd361735a1ade9d8739b9ebe5',
                                                'b7e14fea4413440b9054b7fb1628bb9c545c509c',
                                                'bc5bca53cca350eb90fc9f84c2e37ba6383807c3',
                                                'bf34be058158fd30622601346819d098dc5d623f',
                                                'c642ecf874028c9f41d18d59a9d663c2a954cc45',
                                                'c996d8b9a8f37bd1b4dd7823abc42780b20998f8',
                                                'c996d8b9a8f37bd1b4dd7823abc42780b20998f8',
                                                'd0f2a808b2f0fa6e115cc6f6c84bb4f29aa8af49',
                                                'd1a1d45142ed3969b3cc3964f81e4249f9e49fbf',
                                                'd66ecccd23bfe1d1416d5fb34778002bb488cce1',
                                                'ede178e216b5dd9200cf2c483c746e0672fbe503',
                                                'ef4158c5634e3819f93499d598ca617c29307ffd',
                                                'f4c54050640e7afa4749875cf9b900d42db361c0',
                                                'fa69c87232cd6dac4d7e33e376467724697c43b9',
                                                'ff792c85e60727e66774eb3da8129298690eab0c',

                                                 'ee446fd5e6dafee4a16fd1bd345d2571dcfd6f5d',
                                                 'ee89bd6bc73d1d14555418a2642172448052f1dd',

                                                 'f7018c21350204c4cf628462f229d44d03545254',
                                                 '0c0d06cac63ee327ceaab4b5ffe2206574ab86bd',
                                                 '9a0bf528b4d66b605f02634236da085595c22101'])

# Load patch stack definition
patch_stack_list = parse_patch_stack_definition(repo, args.stack_def_filename)

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

cache_commit_hashes(upstream_candidates, parallelize=True)

evaluation_list = []
for i in stack_candidates:
    evaluation_list += (i, upstream_candidates)

evaluation_result = EvaluationResult()

print('Starting evaluation.')
pool = Pool(cpu_count())
results = pool.map(_evaluate_patch_list_wrapper, evaluation_list)
pool.close()
pool.join()
print('Evaluation completed.')

for result in results:
    evaluation_result.merge(result)

evaluation_result.to_file(args.evaluation_result_filename)

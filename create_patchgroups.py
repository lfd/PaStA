#!/usr/bin/env python3

import argparse
import copy
from git import Repo
from multiprocessing import Pool, cpu_count
from termcolor import colored

from config import *
from EquivalenceClass import EquivalenceClass
from PatchStack import parse_patch_stack_definition, get_commit, get_next_release_date, cache_commit_hashes


def describe_commit(commit_hash):
    if commit_hash in patch_stack_list:
        stack = patch_stack_list.get_stack_of_commit(commit_hash)
        branch_name = stack.stack_name
        release_date = stack.stack_release_date
    else:
        branch_name = 'master'
        release_date = get_next_release_date(repo, commit_hash)

    commit = get_commit(commit_hash)
    author_date = commit.author_date.strftime('%Y-%m-%d')
    commit_date = commit.commit_date.strftime('%Y-%m-%d')
    return commit_hash, (branch_name, author_date, commit_date, release_date)

parser = argparse.ArgumentParser(description='Interactive Rating: Rate evaluation results')
parser.add_argument('-sp', dest='sp_filename', default=SIMILAR_PATCHES_FILE, help='Similar Patches filename')
parser.add_argument('-ur', dest='ur_filename', default=UPSTREAM_RESULT_LOCATION, help='Upstream result file')
parser.add_argument('-cd', dest='cd_filename', default=COMMIT_DESCRIPTION_LOCATION, help='Output: Commit description file')
parser.add_argument('-pg', dest='pg_filename', default=PATCH_GROUPS_LOCATION, help='Output: Patch groups')

args = parser.parse_args()

# Load patch stack definition
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(PATCH_STACK_DEFINITION)

# similar patch groups
similar_patches = EquivalenceClass.from_file(args.sp_filename)

# upstream results
upstream_results = EquivalenceClass.from_file(args.ur_filename)

stack_commit_hashes = patch_stack_list.get_all_commit_hashes()

# create a copy of the similar patch list
patch_groups = copy.deepcopy(similar_patches)

# Insert every single key of the patch stack into the transitive list. Already existing keys will be skipped.
# This results in a list with at least one key for each patch set
for i in stack_commit_hashes:
    patch_groups.insert_single(i)
patch_groups.optimize()

# Merge upstream results and patch group list
for i in upstream_results:

    similar_hashes = set(i)
    if len(similar_hashes) < 2:
        continue

    upstream = None
    for commit_hash in similar_hashes:
        if commit_hash not in stack_commit_hashes:
            # We found the upstream commit hash
            upstream = commit_hash
            break

    if upstream is None:
        raise ValueError('None of the commits is an upstream commit')

    hashes_in_patch_stacks = similar_hashes - set([upstream])

    for hash in hashes_in_patch_stacks:
        patch_groups.set_property(hash, upstream)


num_patch_groups = len(patch_groups.transitive_list)
print('Overall number of patches in all stacks: ' + str(len(stack_commit_hashes)))
print('Number of patches, that appeared more than once in the stack: ' + str(len(similar_patches.transitive_list)))
print('Number of patch groups: ' + str(num_patch_groups))

upstreams = set(filter(None, map(lambda x: x.property, patch_groups)))
upstream_percentage = len(upstreams) / num_patch_groups
print('All in all, %d patches went upstream (%f)' % (len(upstreams), upstream_percentage))

sys.stdout.write('Writing Patch Group file... ')
patch_groups.to_file(args.pg_filename)
print(colored(' [done]', 'green'))

all_commit_hashes = []
for i in patch_groups:
    all_commit_hashes += i
    if i.property:
        all_commit_hashes.append(i.property)
cache_commit_hashes(all_commit_hashes, parallelize=True)

sys.stdout.write('Getting descriptions...')
pool = Pool(cpu_count())
all_description = dict(pool.map(describe_commit, all_commit_hashes))
pool.close()
pool.join()
print(colored(' [done]', 'green'))

sys.stdout.write('Writing commit descriptions file... ')
with open(args.cd_filename, 'w') as f:
    f.write('commit_hash branch_name author_date commit_date release_date\n')
    for commit_hash, info in all_description.items():
        f.write('%s %s %s %s %s\n' % (commit_hash, info[0], info[1], info[2], info[3]))
print(colored(' [done]', 'green'))
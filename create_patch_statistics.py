#!/usr/bin/env python3

import argparse
import copy
from git import Repo
from multiprocessing import Pool, cpu_count

from config import *
from PatchStack import parse_patch_stack_definition
from Tools import TransitiveKeyList


class PatchFlow:
    def __init__(self, invariant, dropped, upstreams, new):
        self.invariant = invariant
        self.dropped = dropped
        self.upstreams = upstreams
        self.new = new


def write_patch_flow_csv(patchflow, filename):
    with open(filename, 'w') as f:
        f.write('versions left_release_date right_release_date num_patches_left num_patches_right invariant dropped new upstream\n')
        for key, pf in patchflow:
            l_stack, r_stack = key
            f.write('"%s <-> %s" %s %s %d %d %d %d %d %d\n' % (l_stack.stack_version, r_stack.stack_version,
                                                         l_stack.stack_release_date, r_stack.stack_release_date,
                                                         l_stack.num_commits(), r_stack.num_commits(),
                                                         len(pf.invariant), len(pf.dropped), len(pf.new), len(pf.upstreams)))


def get_patch_group_ids(patch_groups, commit_list):
    retval = set()
    for i in commit_list:
        equivalent_id = patch_groups.get_equivalence_id(i)
        if equivalent_id is None:
            raise ValueError('commit not in patch group')

        retval.add(equivalent_id)
    return retval


def analyse_patch_flow(l, r, verbose=False):
    lcommits = get_patch_group_ids(patch_groups, l.commit_hashes)
    rcommits = get_patch_group_ids(patch_groups, r.commit_hashes)

    if verbose:
        print('Comparing %s <-> %s' % (l, r))

    # Surviving invariant patches
    # This is a dictionary from a left-side commit hash to a set of right-side patches
    invariant = set()
    # Dropped patches
    dropped = set()
    # Patches that went upstream
    upstreams = set()
    # New patches
    new = copy.deepcopy(rcommits)

    # Iterate over all commits on the left stack side
    for lcommit in lcommits:

        # If the set is not empty, the patch survived. Otherwise the patch was either dropped or
        # or the patch went upstream.
        if lcommit in rcommits:
            invariant.add(lcommit)
            new.remove(lcommit)
        else:
            upstream = patch_groups.get_property_by_id(lcommit)
            # Did the patch go upstream? Otherwise it was dropped.
            if upstream:
                upstreams.add(lcommit)
            else:
                dropped.add(lcommit)

    if verbose:
        print('Invariant: %d\nDropped: %d\nNew: %d\nUpstream: %d' % (len(invariant),
                                                                     len(dropped),
                                                                     len(new),
                                                                     len(upstreams)))
        print()

    key = l, r
    value = PatchFlow(invariant, dropped, upstreams, new)
    return key, value


def _analyse_patch_flow_helper(args):
    return analyse_patch_flow(*args)

parser = argparse.ArgumentParser(description='Interactive Rating: Rate evaluation results')
parser.add_argument('-pg', dest='pg_filename', default=PATCH_GROUPS_LOCATION, help='Patch group file')
parser.add_argument('-pf', dest='pf_filename', default=PATCH_FLOW_LOCATION, help='Output: Patch Flow file for R')

args = parser.parse_args()

# Load patch stack definition
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

patch_groups = TransitiveKeyList.from_file(args.pg_filename, must_exist=True)

todo = []
for i in range(0, len(patch_stack_list)-1):
    todo.append((patch_stack_list[i], patch_stack_list[i+1]))

pool = Pool(cpu_count())
patchflow = pool.map(_analyse_patch_flow_helper, todo)
pool.close()
pool.join()

write_patch_flow_csv(patchflow, args.pf_filename)

#!/usr/bin/env python3

import argparse
import copy
from git import Repo

from config import *
from PatchStack import parse_patch_stack_definition
from Tools import TransitiveKeyList


def analyse_patch_flow(l, r, verbose=False):
    lcommits = l.commit_hashes
    rcommits = r.commit_hashes

    print('Comparing ' + str(l) + ' <-> ' + str(r))

    # Surviving invariant patches
    # This is a dictionary from a left-side commit hash to a set of right-side patches
    invariant = dict()
    # Dropped patches
    dropped = set()
    # Patches that went upstream
    upstreams = dict()
    # New patches
    new = copy.deepcopy(rcommits)

    # Iterate over all commits on the left stack side
    for lcommit in lcommits:
        # Check if lcommit is in the patch group. This check should never fail.
        if lcommit not in patch_groups:
            raise ValueError('lcommit not in patch group')

        # Get all related commit hashes of that group
        related_to_lcommit = patch_groups.get_commit_hashes(lcommit)

        # The intersection of related_to_lcommit and rcommits denotes the relation of
        # lcommit to a set of patches in rcommits. Beware that this set may contain more than one element!
        # This might be the case, if a patch is e.g. split into several further commits
        intersect = related_to_lcommit & rcommits

        # If the set is not empty, the patch survived. Otherwise the patch was either dropped or
        # or the patch went upstream.
        if len(intersect):
            # TBD! THINK! Anything special in this case? Actually not...
            #if len(intersect) > 1:
            #    print()
            invariant[lcommit] = intersect
            new -= intersect
        else:
            upstream = patch_groups.get_property(lcommit)
            # Did the patch go upstream? Otherwise it was dropped.
            if upstream:
                upstreams[lcommit] = upstream
            else:
                dropped.add(lcommit)

    if verbose:
        print('Invariant: %d\nDropped: %d\nNew: %d\nUpstream: %d' % (len(invariant),
                                                                     len(dropped),
                                                                     len(new),
                                                                     len(upstreams)))
        print()

    key = l, r
    value = invariant, dropped, upstreams, new
    return key, value


parser = argparse.ArgumentParser(description='Interactive Rating: Rate evaluation results')
parser.add_argument('-pg', dest='pg_filename', default=PATCH_GROUPS_LOCATION, help='Patch group file')
parser.add_argument('-pf', dest='pf_filename', default=PATCH_FLOW_LOCATION, help='Output: Patch Flow file for R')

args = parser.parse_args()

# Load patch stack definition
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)

patch_groups = TransitiveKeyList.from_file(args.pg_filename, must_exist=True)

patchflow = []
for i in range(0, len(patch_stack_list)-1):
    retval = analyse_patch_flow(patch_stack_list[i], patch_stack_list[i+1], verbose=True)
    patchflow.append(retval)

with open(args.pf_filename, 'w') as f:
    f.write('left_hand right_hand left_release_date right_release_date invariant dropped new upstream\n')
    for key, value in patchflow:
        l_stack, r_stack = key
        invariant, dropped, upstreams, new = value
        f.write('%s %s %s %s %d %d %d %d\n' % (l_stack.stack_version, r_stack.stack_version,
                                               l_stack.stack_release_date, r_stack.stack_release_date,
                                               len(invariant), len(dropped), len(new), len(upstreams)))

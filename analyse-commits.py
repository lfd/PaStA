#!/usr/bin/env python

from git import Repo

from PatchStack import KernelVersion, parse_patch_stack_definition
from config import *


def analyse_num_commits(patch_stack_list):

    # Create data file
    cur_version = KernelVersion('0.1')
    xtics = []
    data = {}

    for patch_stack in patch_stack_list:

        # TBD! This is linux kernel specific
        if patch_stack.stack_version.base_version_equals(KernelVersion('2.6'), 2):
            num_major = 3
        else:
            num_major = 2

        if not patch_stack.stack_version.base_version_equals(cur_version, num_major):
            xtics.append((patch_stack.stack_version, patch_stack.stack_release_date, patch_stack.num_commits()))
            cur_version = patch_stack.stack_version
            data[cur_version.base_string()] = []

        data[cur_version.base_string()].append('"%s" "%s" %s "%s" %s %d' % (patch_stack.stack_version.base_string(2),
                                                                                patch_stack.base_version,
                                                                                patch_stack.base_release_date,
                                                                                patch_stack.stack_version,
                                                                                patch_stack.stack_release_date,
                                                                                patch_stack.num_commits()))

    for key, value in data.items():
        f = open(GNUPLOT_PREFIX + COMMITCOUNT_PREFIX + key, 'w')
        f.write('basbaseVersion baseVersion baseReleaseDate patchVersion patchReleaseDate numCommits\n')
        sum = "\n".join(value) + '\n'
        f.write(sum)
        f.close()

    # set special xtics
    for tic in xtics:
        print("set xtics add ('%s')" % tic[1])

    for tic in xtics:
        print("set label '%s'\tat '%s', %d offset -4, -1" % tic)


# Main
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION)
# Run analyse_num_commits on the patchstack
analyse_num_commits(patch_stack_list)

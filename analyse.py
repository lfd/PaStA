#!/usr/bin/env python

from git import Repo
from PatchStack import PatchStack, KernelVersion, VersionPoint, parse_patch_stack_definition

BRANCH_PREFIX = 'analysis-'
BASE_PREFIX = 'v'
REPO_LOCATION = './linux/'

GNUPLOT_PREFIX = './plots/'
COMMITCOUNT_PREFIX = 'commitcount-'
PATCH_STACK_DEFINITION = './resources/patch-stack-definition.dat'


def analyse_num_commits(patch_stack_list):

    # Create data file
    cur_version = KernelVersion('0.1')
    xtics = []
    data = {}

    for i in patch_stack_list:

        if i.patch_version.base_version_equals(KernelVersion('2.6'), 2):
            num_major = 3
        else:
            num_major = 2

        if not i.patch_version.base_version_equals(cur_version, num_major):
            xtics.append((i.patch.version, i.patch.release_date, i.num_commits()))
            cur_version = i.patch_version
            data[cur_version.base_string()] = []

        data[cur_version.base_string()].append('"' +
                                               i.patch_version.base_string(2) + '" ' +
                                               '"' + i.base.version + '" ' +
                                               i.base.release_date + ' ' +
                                               '"' + i.patch.version + '" ' +
                                               i.patch.release_date + ' ' +
                                               str(i.num_commits()))

    for key, value in data.items():
        f = open(GNUPLOT_PREFIX + COMMITCOUNT_PREFIX + key, 'w')
        f.write('basbaseVersion baseVersion baseReleaseDate patchVersion patchReleaseDate numCommits\n')
        sum = "\n".join(value) + '\n'
        f.write(sum)
        f.close()

    # set special xtics
    for tic in xtics:
        print("set xtics add ('" + tic[1] + "')")

    for tic in xtics:
        print("set label '" + tic[0] + "'\tat '" + tic[1] + "', " + str(tic[2]) + " offset -4, -1")


# Main
repo = Repo(REPO_LOCATION)
patch_stack_list = parse_patch_stack_definition(repo, PATCH_STACK_DEFINITION, cache=False)
# Run analyse_num_commits on the patchstack
analyse_num_commits(patch_stack_list)

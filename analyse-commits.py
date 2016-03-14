#!/usr/bin/env python3

from git import Repo

from PatchStack import parse_patch_stack_definition
from config import *


def analyse_num_commits(patch_stack_list):
    dt = lambda x : x.strftime('%Y-%m-%d')
    for header, patch_stack_group in patch_stack_list.iter_groups():
        data = []
        for patch_stack in patch_stack_group:
            data.append('"%s" %s "%s" %s %d' % (patch_stack.stack_version,
                                                dt(patch_stack.stack_release_date),
                                                patch_stack.base_version,
                                                dt(patch_stack.base_release_date),
                                                patch_stack.num_commits()))

        with open(GNUPLOT_PREFIX + COMMITCOUNT_PREFIX + header, 'w') as f:
            f.write('stackVersion stackReleaseDate baseVersion baseReleaseDate numCommits\n')
            sum = "\n".join(data) + '\n'
            f.write(sum)


def main():
    repo = Repo(REPO_LOCATION)
    patch_stack_list = parse_patch_stack_definition(PATCH_STACK_DEFINITION)

    # Create destination directory if not existing
    if not os.path.exists(GNUPLOT_PREFIX):
        os.makedirs(GNUPLOT_PREFIX)

    # Run analyse_num_commits on the patchstack
    analyse_num_commits(patch_stack_list)


if __name__ == '__main__':
    main()
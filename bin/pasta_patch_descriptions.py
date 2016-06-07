#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import argparse
import os
import sys

from datetime import datetime
from multiprocessing import Pool, cpu_count
from termcolor import colored

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *

# In this case, we have to use GitPython as pygit2 does not support describe --contains
import git as gitpython


my_repo = gitpython.Repo(config.repo_location)


def get_next_release_date(commit_hash):
    description = my_repo.git.describe('--contains', commit_hash)
    description = description.split('~')[0]

    timestamp = repo.lookup_reference('refs/tags/' + description).get_object().commit_time
    return datetime.fromtimestamp(int(timestamp))


def describe_commit(commit_hash):
    if commit_hash in patch_stack_definition:
        stack = patch_stack_definition.get_stack_of_commit(commit_hash)
        branch_name = stack.stack_name
        release_date = stack.stack_release_date
    else:
        branch_name = 'master'
        release_date = get_next_release_date(commit_hash)

    commit = get_commit(commit_hash)
    release_date = format_date_ymd(release_date)
    author_date = format_date_ymd(commit.author_date)
    commit_date = format_date_ymd(commit.commit_date)
    return commit_hash, (branch_name, author_date, commit_date, release_date)


def patch_descriptions(prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-cd', dest='cd_filename', metavar='filename',
                        default=config.commit_description, help='Output: Commit description file')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=config.patch_groups, help='Output: Patch groups')
    args = parser.parse_args(argv)

    # similar patch groups
    patch_groups = EquivalenceClass.from_file(args.pg_filename)

    all_commit_hashes = []
    for i in patch_groups:
        all_commit_hashes += i
        if i.property:
            all_commit_hashes.append(i.property)
    cache_commits(all_commit_hashes, parallelise=True)

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


if __name__ == '__main__':
    patch_descriptions(sys.argv[0], sys.argv[1:])

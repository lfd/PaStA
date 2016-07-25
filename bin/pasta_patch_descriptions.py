#!/usr/bin/env python3

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import os
import sys

from datetime import datetime
from multiprocessing import Pool, cpu_count
from termcolor import colored

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from PaStA import *

# In this case, we have to use GitPython as pygit2 does not support describe --contains
import git as gitpython


_config = None
_tmp_repo = None


def get_next_release_date(repo, gitpython_repo, commit_hash):
    description = gitpython_repo.git.describe('--contains', commit_hash)
    description = description.split('~')[0]

    timestamp = repo.repo.lookup_reference('refs/tags/' + description).get_object().commit_time
    return datetime.fromtimestamp(int(timestamp))


def describe_commit(commit):
    psd = _config.psd
    repo = _config.repo
    gitpython_repo = _tmp_repo

    commit_hash = commit.commit_hash

    if commit_hash in psd:
        stack = psd.get_stack_of_commit(commit_hash)
        branch_name = stack.stack_name
        release_date = stack.stack_release_date
    else:
        branch_name = 'master'
        release_date = get_next_release_date(repo, gitpython_repo, commit_hash)

    release_date = format_date_ymd(release_date)
    author_date = format_date_ymd(commit.author_date)
    commit_date = format_date_ymd(commit.commit_date)
    return commit_hash, (branch_name, author_date, commit_date, release_date)


def patch_descriptions(config, prog, argv):
    parser = argparse.ArgumentParser(prog=prog, description='Interactive Rating: Rate evaluation results')
    parser.add_argument('-cd', dest='cd_filename', metavar='filename',
                        default=config.commit_description, help='Output: Commit description file')
    parser.add_argument('-pg', dest='pg_filename', metavar='filename',
                        default=config.patch_groups, help='Patch groups filename (optional)')
    args = parser.parse_args(argv)

    repo = config.repo
    global _tmp_repo
    _tmp_repo = gitpython.Repo(config.repo_location)
    global _config
    _config = config

    # similar patch groups
    patch_groups = EquivalenceClass.from_file(args.pg_filename, must_exist=True)

    # We can at least cache all commits on the patch stacks
    repo.load_commit_cache(config.commit_cache_stack_filename)
    all_commit_hashes = []
    for i in patch_groups:
        all_commit_hashes += i
        if i.property:
            all_commit_hashes.append(i.property)
    repo.cache_commits(all_commit_hashes, parallelise=True)

    all_commits = [repo[x] for x in all_commit_hashes]

    sys.stdout.write('Getting descriptions...')
    pool = Pool(cpu_count(), maxtasksperchild=1)
    all_description = dict(pool.map(describe_commit, all_commits, chunksize=1000))
    pool.close()
    pool.join()
    print(colored(' [done]', 'green'))

    _tmp_repo = None
    _config = None

    sys.stdout.write('Writing commit descriptions file...')
    with open(args.cd_filename, 'w') as f:
        f.write('commit_hash branch_name author_date commit_date release_date\n')
        for commit_hash, info in all_description.items():
            f.write('%s %s %s %s %s\n' % (commit_hash, info[0], info[1], info[2], info[3]))
    print(colored(' [done]', 'green'))


if __name__ == '__main__':
    config = Config(sys.argv[1])
    patch_descriptions(config, sys.argv[0], sys.argv[2:])

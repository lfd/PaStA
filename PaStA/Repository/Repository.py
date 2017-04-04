"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import pickle
import pygit2
import sys

from datetime import datetime
from multiprocessing import Pool, cpu_count
from termcolor import colored

from .Commit import Commit

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


def _retrieve_commit(repo, commit_hash):
    commit = repo[commit_hash]

    author_date = datetime.fromtimestamp(commit.author.time)
    commit_date = datetime.fromtimestamp(commit.commit_time)

    # Respect timezone offsets?
    return Commit(commit_hash,
                  commit.message,
                  _retrieve_diff(repo, commit_hash),
                  commit.author.name, commit.author.email, author_date,
                  commit.committer.name, commit.committer.email, commit_date)


def _retrieve_diff(repo, commit_hash):
    commit = repo[commit_hash]
    if len(commit.parents) == 1:
        diff = repo.diff(commit.parents[0], commit).patch
    else:
        # Filter merge commits and commits with no parents
        diff = None
    return diff or ''


def _retrieve_commit_subst(commit_hash):
    return commit_hash, _retrieve_commit(_tmp_repo, commit_hash)


class Repository:
    def __init__(self, repo_location):
        self.repo_location = repo_location
        self.ccache = {}
        self.repo = pygit2.Repository(repo_location)

    def inject_commits(self, commit_dict):
        for key, val in commit_dict.items():
            self.ccache[key] = val

    def clear_commit_cache(self):
        self.ccache.clear()

    def get_commit(self, commit_hash):
        """
        Return a particular commit
        :param commit_hash: commit hash
        :return: Commit object
        """

        # simply return commit if it is already cached
        if commit_hash in self.ccache:
            return self.ccache[commit_hash]

        # cache and return if it is not yet cached
        self.ccache[commit_hash] = _retrieve_commit(self.repo, commit_hash)
        return self.ccache[commit_hash]

    def load_ccache(self, f_ccache, must_exist=False):
        print('Loading commit cache file %s...' % f_ccache)
        try:
            with open(f_ccache, 'rb') as f:
                this_commits = pickle.load(f)
            print('Loaded %d commits from cache file' % len(this_commits))
            self.inject_commits(this_commits)
            return set(this_commits.keys())
        except FileNotFoundError:
            if must_exist:
                raise
            print('Warning, commit cache file %s not found!' % f_ccache)
            return set()

    def export_ccache(self, f_ccache):
        print('Writing %d commits to cache file' % len(self.ccache))
        with open(f_ccache, 'wb') as f:
            pickle.dump(self.ccache, f, pickle.HIGHEST_PROTOCOL)

    def cache_commits(self, commit_hashes, parallelise=True, cpu_factor = 1):
        """
        Caches a list of commit hashes
        :param commit_hashes: List of commit hashes
        :param parallelise: parallelise
        """
        num_cpus = int(cpu_factor * cpu_count())
        # deactivate parallelistation, if we only have a single CPU
        if num_cpus <= 1:
            parallelise = False
        already_cached = set(self.ccache.keys())
        worklist = set(commit_hashes) - already_cached

        if len(worklist) == 0:
            return

        sys.stdout.write('Caching %d/%d commits. This may take a while...' %
                         (len(worklist), len(commit_hashes)))
        sys.stdout.flush()

        if parallelise:
            global _tmp_repo
            _tmp_repo = self.repo

            p = Pool(num_cpus, maxtasksperchild=10)
            result = p.map(_retrieve_commit_subst, worklist, chunksize=100)
            p.close()
            p.join()

            _tmp_repo = None
        else:
            result = map(lambda x: (x, _retrieve_commit(self.repo, x)),
                         worklist)

        result = dict(result)
        self.inject_commits(result)
        print(colored(' [done]', 'green'))

    def __getitem__(self, item):
        return self.get_commit(item)

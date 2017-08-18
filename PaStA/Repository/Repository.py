"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import git
import os
import pickle
import pygit2
import sys

from datetime import datetime
from multiprocessing import Pool, cpu_count
from termcolor import colored

from .Commit import Commit
from .Mbox import mbox_load_index, parse_mail

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


def _retrieve_commit_repo(repo, commit_hash):
    if commit_hash not in repo:
        return None

    commit = repo[commit_hash]

    author_date = datetime.fromtimestamp(commit.author.time)
    commit_date = datetime.fromtimestamp(commit.commit_time)

    # Respect timezone offsets?
    return Commit(commit_hash,
                  commit.message,
                  _retrieve_diff(repo, commit_hash),
                  commit.author.name, commit.author.email, author_date,
                  commit.committer.name, commit.committer.email, commit_date)


def _retrieve_commit_mail(repo, message_id):
    index = repo.mbox_index[message_id]
    ret = parse_mail(repo.d_mbox_split, (message_id, index))
    if not ret:
        return None

    _, commit = ret

    return commit


def _retrieve_diff(repo, commit_hash):
    commit = repo[commit_hash]
    if len(commit.parents) == 1:
        diff = repo.diff(commit.parents[0], commit).patch
    else:
        # Filter merge commits and commits with no parents
        diff = None
    return diff or ''


def _load_commit_subst(commit_hash):
    return commit_hash, _tmp_repo._load_commit(commit_hash)


class Repository:
    def __init__(self, repo_location):
        self.repo_location = repo_location
        self.ccache = {}
        self.repo = pygit2.Repository(repo_location)
        self.mbox_index = None
        self.d_mbox_split = None

    def inject_commits(self, commit_dict):
        for key, val in commit_dict.items():
            self.ccache[key] = val

    def clear_commit_cache(self):
        self.ccache.clear()

    def _load_commit(self, commit_hash):
        # check if the victim is an email
        if commit_hash[0] == '<':
            return _retrieve_commit_mail(self, commit_hash)
        else:
            return _retrieve_commit_repo(self.repo, commit_hash)

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
        commit = self._load_commit(commit_hash)
        if commit is None:
            raise KeyError('Commit or Mail not found: %s' % commit_hash)

        # store commit in local cache
        self.ccache[commit_hash] = commit

        return commit

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
            _tmp_repo = self

            p = Pool(num_cpus, maxtasksperchild=10)
            result = p.map(_load_commit_subst, worklist, chunksize=100)
            p.close()
            p.join()

            _tmp_repo = None
        else:
            result = map(lambda x: (x, self._load_commit(x)),
                         worklist)

        result = {key: value for (key, value) in result if value is not None}

        self.inject_commits(result)
        print(colored(' [done]', 'green'))

    def __getitem__(self, item):
        return self.get_commit(item)

    def get_commithash_range(self, range):
        """
        Gets all commithashes within a certain range
        """
        if range[0] is None:
            range = range[1]
        else:
            range = '%s..%s' % range

        # we use git.Repo, as pygit doesn't support this nifty log functionality
        repo = git.Repo(self.repo_location)

        upstream_hashes = repo.git.log('--pretty=format:%H', range)
        upstream_hashes = upstream_hashes.splitlines()
        return upstream_hashes

    def get_commits_on_stack(self, base, stack):
        """
        Returns the commit hashes on a patch stack
        """
        stack_list = self.get_commithash_range((None, stack))
        base_set = set(self.get_commithash_range((None, base)))

        # Preserve order!
        retval = []
        for stack_hash in stack_list:
            if stack_hash not in base_set:
                retval.append(stack_hash)
        return retval

    def register_mailbox(self, d_mbox_split, f_mbox_index, f_mbox):
        # check if mailbox is already prepared
        if os.path.isfile(f_mbox_index):
            self.d_mbox_split = d_mbox_split
            self.mbox_index = mbox_load_index(f_mbox_index)
            return True

        return False

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import gc
import git
import os
import pickle
import pygit2

from multiprocessing import Pool, cpu_count
from subprocess import call

from .Commit import Commit
from .Mbox import mbox_load_index, parse_mail
from ..Util import done, printn

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


def _retrieve_commit_repo(repo, commit_hash):
    if commit_hash not in repo:
        return None

    return Commit(repo, commit_hash)


def _retrieve_commit_mail(repo, message_id):
    filename = repo.get_mail_filename(message_id)

    ret = parse_mail(filename)
    if not ret:
        return None

    _, commit = ret

    return commit


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
        # use commit.commit_hash instead of commit_hash, because commit_hash
        # might be abbreviated.
        self.ccache[commit.commit_hash] = commit

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

    def cache_evict_except(self, commit_except):
        victims = self.ccache.keys() - commit_except
        print('Evicting %d commits from cache' % len(victims))
        for victim in victims:
            del self.ccache[victim]
        gc.collect()

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
        commit_hashes = set(commit_hashes)
        worklist = commit_hashes - already_cached

        if len(worklist) == 0:
            return commit_hashes, set()

        printn('Caching %d/%d commits. This may take a while...' %
                         (len(worklist), len(commit_hashes)))

        if parallelise:
            global _tmp_repo
            _tmp_repo = self

            p = Pool(num_cpus, maxtasksperchild=10)
            result = p.map(_load_commit_subst, worklist, chunksize=100)
            p.close()
            p.join()

            _tmp_repo = None
        else:
            result = list(map(lambda x: (x, self._load_commit(x)), worklist))

        invalid = {key for (key, value) in result if value is None}
        result = {key: value for (key, value) in result if value is not None}

        self.inject_commits(result)
        done()

        return set(result.keys()), invalid

    def __getitem__(self, item):
        return self.get_commit(item)

    def __contains__(self, item):
        if item in self.mbox_index:
            return True

        try:
            return item in self.repo
        except:
            return False

    def get_commithash_range(self, range):
        """
        Gets all commithashes within a certain range
        Usage: get_commithash_range('v2.0..v2.1')
               get_commithash_ranse('v3.0')
        """

        # we use git.Repo, as pygit doesn't support this nifty log functionality
        repo = git.Repo(self.repo_location)
        return repo.git.log('--pretty=format:%H', range).splitlines()

    def get_commits_on_stack(self, base, stack):
        """
        Returns the commit hashes on a patch stack
        """
        stack_list = self.get_commithash_range(stack)
        base_set = set(self.get_commithash_range(base))

        # Preserve order!
        retval = []
        for stack_hash in stack_list:
            if stack_hash not in base_set:
                retval.append(stack_hash)
        return retval

    def register_mailbox(self, d_mbox_split, f_mbox_index, f_mbox):
        # check if mailbox is already prepared
        if not os.path.isfile(f_mbox_index) and os.path.isfile(f_mbox):
            printn('Processing Mailbox...')
            cwd = os.getcwd()
            os.chdir(os.path.join(cwd, 'tools'))
            call(['./process_mailbox.sh', f_mbox, d_mbox_split])
            os.chdir(cwd)
            done()

        if os.path.isfile(f_mbox_index):
            self.d_mbox_split = d_mbox_split
            printn('Loading Mailbox index...')
            self.mbox_index = mbox_load_index(f_mbox_index)
            done()
            return True

        return False

    def get_mail_filename(self, message_id):
        _, date_str, md5 = self.mbox_index[message_id]
        return os.path.join(self.d_mbox_split, date_str, md5)

    def mbox_get_message_ids(self, time_window):
        return [x[0] for x in self.mbox_index.items()
                if time_window[0] <= x[1][0] <= time_window[1]]

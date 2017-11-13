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
import pickle
import pygit2

from datetime import datetime, timezone, timedelta
from logging import getLogger
from multiprocessing import Pool, cpu_count

from .MessageDiff import MessageDiff
from .Mbox import Mbox, PatchMail
from ..Util import fix_encoding

log = getLogger(__name__[-15:])

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None


class Commit(MessageDiff):
    def __init__(self, repo, commit_hash):
        commit = repo[commit_hash]

        auth_tz = timezone(timedelta(minutes=commit.author.offset))
        commit_tz = timezone(timedelta(minutes=commit.commit_time_offset))

        author_date = datetime.fromtimestamp(commit.author.time, auth_tz)
        commit_date = datetime.fromtimestamp(commit.commit_time, commit_tz)

        # default: diff is empty. This filters merge commits and commits with no
        # parents
        diff = ''
        if len(commit.parents) == 1:
            diff = repo.diff(commit.parents[0], commit).patch
            # there may be empty commits
            if not diff:
                diff = ''

        self.commit_hash = commit.hex

        self.committer = commit.committer.name
        self.committer_email = commit.committer.email
        self.commit_date = commit_date

        super(Commit, self).__init__(commit.message, diff, commit.author.name,
                                     commit.author.email, author_date)

    def format_message(self):
        custom = ['Committer:  %s <%s>' %
                  (fix_encoding(self.committer), self.committer_email),
                  'CommitDate: %s' % self.commit_date]
        return super(Commit, self).format_message(custom)


def _load_commit_subst(commit_hash):
    return commit_hash, _tmp_repo._load_commit(commit_hash)


class Repository:
    def __init__(self, repo_location):
        self.repo_location = repo_location
        self.ccache = {}
        self.repo = pygit2.Repository(repo_location)
        self.mbox = None

    def _inject_commits(self, commit_dict):
        for key, val in commit_dict.items():
            self.ccache[key] = val

    def clear_commit_cache(self):
        self.ccache.clear()

    def _load_commit(self, commit_hash):
        # check if the victim is an email
        try:
            if commit_hash[0] == '<':
                return PatchMail(self.mbox[commit_hash])
            else:
                return Commit(self.repo, commit_hash)
        except Exception as e:
            log.warning('Unable to load commit %s: %s' % (commit_hash, str(e)))
            return None

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
        log.info('Loading commit cache file %s' % f_ccache)
        try:
            with open(f_ccache, 'rb') as f:
                this_commits = pickle.load(f)
                log.info('  ↪ Loaded %d commits from cache file' % len(this_commits))
            self._inject_commits(this_commits)
            return set(this_commits.keys())
        except FileNotFoundError:
            if must_exist:
                raise
                log.info('  ↪ Warning, commit cache file %s not found!' % f_ccache)
            return set()

    def export_ccache(self, f_ccache):
        log.info('Writing %d commits to cache file' % len(self.ccache))
        with open(f_ccache, 'wb') as f:
            pickle.dump(self.ccache, f, pickle.HIGHEST_PROTOCOL)

    def cache_evict_except(self, commit_except):
        victims = self.ccache.keys() - commit_except
        log.info('Evicting %d commits from cache' % len(victims))
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

        log.info('Caching %d/%d commits' % (len(worklist), len(commit_hashes)))

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

        if self.mbox:
            invalid_mail = {x for x in invalid if x[0] == '<'}
            self.mbox.invalidate(invalid_mail)

        self._inject_commits(result)
        log.info('  ↪ done')

        return commit_hashes - invalid, invalid

    def __getitem__(self, item):
        return self.get_commit(item)

    def __contains__(self, item):
        if self.mbox and item in self.mbox:
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

    def register_mailbox(self, d_mbox):
        try:
            self.mbox = Mbox(d_mbox)
        except Exception as e:
            log.error('Unable to load mailbox: %s' % str(e))
            log.error('Did you forget to run \'pasta mbox_prepare\'?')
            quit(-1)
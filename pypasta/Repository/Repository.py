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
from tqdm import tqdm

from .MessageDiff import MessageDiff
from .Mbox import Mbox, PatchMail
from ..Util import fix_encoding, get_commit_hash_range

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

        self.committer = fix_encoding(commit.committer.raw_name)
        self.committer_email = commit.committer.email
        self.commit_date = commit_date

        # split message and diff at newlines
        message = fix_encoding(commit.raw_message).split('\n')
        diff = diff.split('\n')

        author_name = fix_encoding(commit.author.raw_name)

        content = message, None, diff

        super(Commit, self).__init__(content, author_name, commit.author.email,
                                     author_date)

    def format_message(self):
        custom = ['Committer:  %s <%s>' %
                  (self.committer, self.committer_email),
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
                return self.mbox[commit_hash]
            else:
                return Commit(self.repo, commit_hash)
        except Exception as e:
            log.debug('Unable to load commit %s: %s' % (commit_hash, str(e)))
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

    def load_ccache(self, f_ccache):
        log.info('Loading commit cache file %s' % f_ccache)
        try:
            with open(f_ccache, 'rb') as f:
                this_commits = pickle.load(f)
                log.info('  ↪ Loaded %d commits from cache file' % len(this_commits))
            self._inject_commits(this_commits)
            return set(this_commits.keys())
        except FileNotFoundError:
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

            with Pool(num_cpus, maxtasksperchild=10) as p:
                result = list(tqdm(p.imap(_load_commit_subst, worklist,
                                          chunksize=100),
                                   total=len(worklist)))

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

    def get_raw(self, item):
        if self.mbox and item in self.mbox:
            return self.mbox.get_raw(item)

        commit = self[item]
        return '\n'.join(commit.format_message() + commit.diff.raw)

    def get_commithash_range(self, range):
        return get_commit_hash_range(self.repo_location, range)

    def cherry(self, base, stack):
        """
        Returns the commit hashes on a patch stack
        """
        repo = git.Repo(self.repo_location)
        cherries = repo.git.cherry(base, stack).splitlines()
        cherries = [x.split() for x in cherries]

        has_removals = '-' in [x[0] for x in cherries]
        if has_removals:
            log.warning('Removals in patch stacks are not implemented!')

        inserted_cherries = [x[1] for x in cherries]

        # preserve order
        return list(reversed(inserted_cherries))

    def mbox_register(self, config):
        if not self.mbox:
            self.mbox = Mbox(config)

    def mbox_update(self, config):
        self.mbox_register(config)
        self.mbox.update()

        # The mbox doesn't track changes after an update. The easiest
        # workaround is to reload the whole instance.
        del self.mbox
        self.mbox = None
        self.mbox_register(config)

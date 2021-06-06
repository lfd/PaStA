"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import gc
import git
import pickle
import pygit2
import re

from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from .MessageDiff import MessageDiff, Signature
from .Mbox import Mbox
from ..Util import fix_encoding, get_commit_hash_range,\
                   pygit2_signature_to_datetime

log = getLogger(__name__[-15:])

# We need this global variable, as pygit2 Repository objects are not pickleable
_tmp_repo = None

mainline_regex = {
    'linux': re.compile(r'^v(\d+\.\d+|2\.6\.\d+)(-rc\d+)?$'),
    'qemu': re.compile(r'^v.*$'),
    'u-boot': re.compile(r'^v201.*$'),
    'xen': re.compile(r'^(RELEASE-)?\d+\.\d+\.0.*$'),
}


class PygitCredentials(pygit2.RemoteCallbacks):
    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types & pygit2.credentials.GIT_CREDTYPE_SSH_KEY:
            return pygit2.KeypairFromAgent(username_from_url)
        else:
            return None


class Commit(MessageDiff):
    @staticmethod
    def get_signature(pygit_person):
        return Signature(fix_encoding(pygit_person.raw_name),
                         pygit_person.email,
                         pygit2_signature_to_datetime(pygit_person))

    def __init__(self, repo, commit_hash):
        commit = repo[commit_hash]

        author = Commit.get_signature(commit.author)
        self.committer = Commit.get_signature(commit.committer)

        # default: diff is empty. This filters merge commits and commits with no
        # parents
        diff = ''
        if len(commit.parents) == 1:
            diff = repo.diff(commit.parents[0], commit)
            diff.find_similar()
            diff = diff.patch
            # there may be empty commits
            if not diff:
                diff = ''

        # split message and diff at newlines
        message = fix_encoding(commit.raw_message).split('\n')
        diff = diff.split('\n')

        content = message, None, diff

        super(Commit, self).__init__(commit.hex, content, author)

    def format_message(self):
        custom = ['Committer:  %s <%s>' %
                  (self.committer.name, self.committer.email),
                  'CommitDate: %s' % self.committer.date]
        return super(Commit, self).format_message(custom)


def _load_commit_subst(commit_hash):
    return commit_hash, _tmp_repo._load_commit(commit_hash)


class Repository:
    REGEX_TAGS = re.compile('^refs/tags')

    def __init__(self, project_name, repo_location):
        self.repo_location = repo_location
        self.ccache = {}
        self.repo = pygit2.Repository(repo_location)
        self.mbox = None

        self.tags = list()
        tag_refs = filter(lambda r: self.REGEX_TAGS.match(r),
                          self.repo.listall_references())
        for tag_ref in tag_refs:
            tag = tag_ref[len('refs/tags/'):]
            ref = self.repo.lookup_reference(tag_ref)
            target = self.repo[ref.target]
            # There are some broken tags in the Linux Kernel (e.g. v2.6.13.4)
            # that point to commits instead of tags. In those cases, we need to
            # treat the tag as a commit.
            if isinstance(target, pygit2.Tag):
                tagger = target.tagger
            elif isinstance(target, pygit2.Commit):
                tagger = target.committer
            else:
                raise NotImplementedError('Unknown tag type')

            if tagger is None:
                continue

            dt = pygit2_signature_to_datetime(tagger)
            self.tags.append((tag, dt))

        # Sort tags - by date
        self.tags.sort(key=lambda x: x[1])

        if project_name not in mainline_regex:
            log.warning('No Version support for %s' % project_name)
            self.mainline_tags = []
            return

        self.mainline_tags = list(filter(
            lambda x : mainline_regex[project_name].match(x[0]), self.tags))

    def patch_get_version(self, patch):
        tag = None
        date = patch.author.date

        # We won't be able to find a valid tag if the author date is older
        # than the first date in self.tags.
        if date < self.mainline_tags[0][1]:
            raise ValueError('Too old: no valid tag found for patch %s' % patch.identifier)

        for cand_tag, cand_tag_date in self.mainline_tags:
            if cand_tag_date > patch.author.date:
                break
            tag = cand_tag

        return tag

    def _inject_commits(self, commit_dict):
        for key, val in commit_dict.items():
            self.ccache[key] = val

    def clear_commit_cache(self):
        self.ccache.clear()

    def _load_commit(self, identifier):
        # check if the victim is an email
        try:
            if identifier[0] == '<':
                return self.mbox[identifier]
            else:
                return Commit(self.repo, identifier)
        except Exception as e:
            log.debug('Unable to load commit %s: %s' % (identifier, str(e)))
            return None

    def get_tree(self, revision):
        target = self.repo.revparse_single(revision)
        if isinstance(target, pygit2.Tag):
            commit = target.get_object()
        else:
            commit = target
        return commit.tree

    def get_blob(self, revision, filename):
        tree = self.get_tree(revision)
        blob_hash = tree[filename].id
        blob = self.repo[blob_hash].data

        return blob

    def get_commit(self, identifier):
        """
        Get a particular commit
        :param identifier: Commit Hash or Message ID
        :return: Commit object
        """

        # simply return commit if it is already cached
        if identifier in self.ccache:
            return self.ccache[identifier]

        # cache and return if it is not yet cached
        commit = self._load_commit(identifier)
        if commit is None:
            raise KeyError('Commit or Mail not found: %s' % identifier)

        # store commit in local cache
        # use commit.identifier instead of identifier, because commit_hash
        # might be abbreviated.
        self.ccache[commit.identifier] = commit

        return commit

    def load_ccache(self, f_ccache, description):
        log.info('Loading %s commit cache' % description)
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
        return victims

    def cache_commits(self, identifiers, parallelise=True, cpu_factor=1):
        """
        Caches a list of commit hashes
        :param identifiers: List of identifiers
        :param parallelise: parallelise
        """
        num_cpus = int(cpu_factor * cpu_count())
        # deactivate parallelistation, if we only have a single CPU
        if num_cpus <= 1:
            parallelise = False
        already_cached = set(self.ccache.keys())
        identifiers = set(identifiers)
        worklist = identifiers - already_cached

        if len(worklist) == 0:
            return identifiers

        log.info('Caching %d/%d commits' % (len(worklist), len(identifiers)))

        if parallelise:
            global _tmp_repo
            _tmp_repo = self

            with Pool(num_cpus, maxtasksperchild=100) as p:
                result = list(tqdm(p.imap(_load_commit_subst, worklist,
                                          chunksize=1000),
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

        return already_cached | set(result.keys())

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

    def register_mbox(self, config):
        if not self.mbox:
            self.mbox = Mbox(config)

    def update_mbox(self, config):
        self.register_mbox(config)
        self.mbox.update()

        # The mbox doesn't track changes after an update. The easiest
        # workaround is to reload the whole instance.
        del self.mbox
        self.mbox = None
        self.register_mbox(config)

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""


import csv
import os
import sys

from datetime import datetime
from multiprocessing import Pool, cpu_count
from termcolor import colored

from PaStA import config, repo
from PaStA.Patch import *

# dictionary for globally cached commits
commits = {}


def get_commits_from_file(filename, ordered=True):
    content = file_to_string(filename, must_exist=True).splitlines()
    # Filter empty lines
    content = filter(None, content)
    # Filter comment lines
    content = filter(lambda x: not x.startswith('#'), content)
    # return filtered list or set
    if ordered == True:
        return list(content)
    else:
        return set(content)


def file_to_string(filename, must_exist=True):
    try:
        # I HATE ENCONDING!
        # Anyway, opening a file as binary and decoding it to iso8859 solves the problem :-)
        with open(filename, 'rb') as f:
            retval = str(f.read().decode('iso8859'))
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise
        return None

    return retval


def format_date_ymd(dt):
    return dt.strftime('%Y-%m-%d')


class Commit:
    COMMIT_HASH_LOCATION = re.compile(r'(..)(..).*')
    SIGN_OFF_REGEX = re.compile((r'^(Signed-off-by:|Acked-by:|Link:|CC:|Reviewed-by:'
                                 r'|Reported-by:|Tested-by:|LKML-Reference:|Patch:)'),
                                re.IGNORECASE)
    REVERT_REGEX = re.compile(r'revert', re.IGNORECASE)

    def __init__(self, commit_hash, message, diff,
                 author, author_email, author_date,
                 committer, committer_email, commit_date):

        self._commit_hash = commit_hash

        if isinstance(message, list):
            self._raw_message = '\n'.join(message)
        else:
            self._raw_message = message

        # Split by linebreaks and filter empty lines
        self._message = list(filter(None, self._raw_message.splitlines()))
        # Filter signed-off-by lines
        self._message = list(filter(lambda x: not Commit.SIGN_OFF_REGEX.match(x), self._message))

        self._committer = committer
        self._committer_email = committer_email
        self._commit_date = datetime.fromtimestamp(commit_date)

        self._author = author
        self._author_email = author_email
        self._author_date = datetime.fromtimestamp(author_date)

        # Is a revert message?
        self._is_revert = bool(Commit.REVERT_REGEX.search(self._raw_message))

        if isinstance(diff, list):
            self._raw_diff = '\n'.join(diff)
            self._diff = Diff.parse_diff_nosplit(diff)
        else:
            self._raw_diff = diff
            self._diff = Diff.parse_diff(diff)

    @staticmethod
    def from_commit_hash(commit_hash):
        commit = repo[commit_hash]

        # Respect timezone offsets?
        return Commit(commit_hash,
                      commit.message,
                      Commit.get_diff(commit_hash),
                      commit.author.name, commit.author.email, commit.author.time,
                      commit.committer.name, commit.committer.email, commit.commit_time)

    @staticmethod
    def get_diff(commit_hash):
        tmp = Commit.COMMIT_HASH_LOCATION.match(commit_hash)
        commit_hash_location = '%s/%s/%s' % (tmp.group(1), tmp.group(2), commit_hash)
        return file_to_string(os.path.join(config.diffs_location, commit_hash_location))

    @property
    def commit_hash(self):
        return self._commit_hash

    @property
    def is_revert(self):
        return self._is_revert

    @property
    def raw_diff(self):
        return self._raw_diff

    @property
    def diff(self):
        return self._diff

    @property
    def raw_message(self):
        return self._raw_message

    @property
    def message(self):
        return self._message

    @property
    def subject(self):
        return self._message[0]

    @property
    def author(self):
        return self._author

    @property
    def author_email(self):
        return self._author_email

    @property
    def author_date(self):
        return self._author_date

    @property
    def committer(self):
        return self._committer

    @property
    def committer_email(self):
        return self._committer_email

    @property
    def commit_date(self):
        return self._commit_date


class VersionPoint:
    def __init__(self, commit, version, release_date):
        self.commit = commit
        self.version = version
        self.release_date = datetime.strptime(release_date, '%Y-%m-%d')


class PatchStack:
    def __init__(self, base, stack, commit_hashes):
        self._base = base
        self._stack = stack
        self._commit_hashes = commit_hashes

    @property
    def commit_hashes(self):
        """
        :return: A copy of the commit hashes list
        """
        return list(self._commit_hashes)

    @property
    def base_version(self):
        return self._base.version

    @property
    def stack_version(self):
        return self._stack.version

    @property
    def stack_release_date(self):
        return self._stack.release_date

    @property
    def base_release_date(self):
        return self._base.release_date

    @property
    def base_name(self):
        return self._base.commit

    @property
    def stack_name(self):
        return self._stack.commit

    def num_commits(self):
        return len(self._commit_hashes)

    def __repr__(self):
        return '%s (%d)' % (self.stack_version, self.num_commits())


class PatchStackDefinition:
    HEADER_NAME_REGEX = re.compile(r'## (.*)')

    def __init__(self, patch_stack_groups, upstream_hashes):
        # List containing all patch stacks, grouped in major versions
        self.patch_stack_groups = patch_stack_groups
        # Set containing all upstream commit hashes
        self._upstream_hashes = upstream_hashes

        # Bidirectional map: each PatchStack is assigned to an identifying number et vice versa
        self._stack_version_to_int = {}

        # This dict is used to map a commit hash to a patch stack
        self._hash_to_version_lookup = {}

        # Set containing all commit hashes on the patch stacks
        self._commits_on_stacks = set()
        cntr = 0
        for i in self:
            self._commits_on_stacks |= set(i.commit_hashes)

            # Allow forward as well as reverse lookups
            self._stack_version_to_int[i] = cntr
            self._stack_version_to_int[cntr] = i
            cntr += 1

            for commit_hash in i.commit_hashes:
                self._hash_to_version_lookup[commit_hash] = i

        # Absolute number of patch stacks
        self._num_stacks = cntr

    @property
    def upstream_hashes(self):
        """
        :return: All upstream commit hashes considered in analysation
        """
        return self._upstream_hashes

    @property
    def commits_on_stacks(self):
        """
        :return: Returns all commit hashes of all patch stacks
        """
        return self._commits_on_stacks

    def get_stack_of_commit(self, commit_hash):
        """
        :param commit_hash: Commit hash
        :return: Returns the patch stack that contains commit hash or None
        """
        return self._hash_to_version_lookup[commit_hash]

    def get_predecessor(self, stack):
        """
        Get the predecessor patch stack of 'stack'
        :param stack: Stack version
        :return: PatchStack predecessing stack or None
        """
        i = self._stack_version_to_int[stack]
        if i == 0:
            return None
        return self._stack_version_to_int[i-1]

    def get_successor(self, stack):
        """
        Get the successor patch stack of 'stack'
        :param stack: Stack version
        :return: PatchStack successing stack or None
        """
        i = self._stack_version_to_int[stack]
        if i >= self._num_stacks - 1:
            return None
        return self._stack_version_to_int[i+1]

    def get_latest_stack(self):
        return self.patch_stack_groups[-1][1][-1]

    def get_oldest_stack(self):
        return self.patch_stack_groups[0][1][0]

    def iter_groups(self):
        for i in self.patch_stack_groups:
            yield i

    def get_stack_by_name(self, name):
        """
        Lookup stack by name
        :param name: stack version
        :return: corresponding patch stack
        """
        for stack in self:
            if stack.stack_version == name:
                return stack
        raise ValueError('Stack not found: %s' % name)

    def is_stack_version_greater(self, lhs, rhs):
        return self._stack_version_to_int[lhs] > self._stack_version_to_int[rhs]

    def __contains__(self, item):
        return item in self._commits_on_stacks

    def __iter__(self):
        for foo, patch_stack_group in self.patch_stack_groups:
            for patch_stack in patch_stack_group:
                yield patch_stack

    @staticmethod
    def parse_definition_file(definition_filename):
        """
        Parses a patch stack definition file
        :param definition_filename: filename of patch stack definition
        :return: PatchStackDefinition
        """
        csv.register_dialect('patchstack', delimiter=' ', quoting=csv.QUOTE_NONE)

        sys.stdout.write('Parsing patch stack definition...')

        with open(definition_filename) as f:
            line_list = f.readlines()

        # Get the global CSV header which is the same for all groups
        csv_header = line_list.pop(0)

        # Filter empty lines
        line_list = list(filter(lambda x: x != '\n', line_list))

        csv_groups = []
        header = None
        for line in line_list:
            if line.startswith('## '):
                if header:
                    csv_groups.append((header, content))
                header = PatchStackDefinition.HEADER_NAME_REGEX.match(line).group(1)
                content = [csv_header]
            elif line.startswith('#'):  # skip comments
                continue
            else:
                content.append(line)

        # Add last group
        if header is not None:
            csv_groups.append((header, content))

        patch_stack_groups = []
        for group_name, csv_list in csv_groups:
            reader = csv.DictReader(csv_list, dialect='patchstack')
            this_group = []
            for row in reader:
                base = VersionPoint(row['BaseCommit'],
                                    row['BaseVersion'],
                                    row['BaseReleaseDate'])

                stack = VersionPoint(row['Branch'],
                                     row['StackVersion'],
                                     row['StackReleaseDate'])

                # get commit hashes of the patch stack
                commit_hashes = get_commits_from_file(os.path.join(config.stack_hashes, stack.version))

                this_group.append(PatchStack(base, stack, commit_hashes))

            patch_stack_groups.append((group_name, this_group))

        # get upstream commit hashes
        upstream = get_commits_from_file(config.upstream_hashes_filename)
        blacklist = get_commits_from_file(config.upstream_blacklist, ordered=False)
        # filter blacklistes commit hashes
        upstream = [x for x in upstream if x not in blacklist]

        # Create patch stack list
        retval = PatchStackDefinition(patch_stack_groups, upstream)
        print(colored(' [done]', 'green'))

        return retval


def get_commit(commit_hash):
    """
    Return a particular commit
    :param commit_hash: commit hash
    :return: commit
    """

    # simply return commit if it is already cached
    if commit_hash in commits:
        return commits[commit_hash]

    # cache and return if it is not yet cached
    commits[commit_hash] = Commit.from_commit_hash(commit_hash)
    return commits[commit_hash]


def commit_from_commit_hash(commit_hash):
    return commit_hash, Commit.from_commit_hash(commit_hash)


def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]


def cache_commits(commit_hashes, parallelise=True):
    """
    Caches a list of commit hashes
    :param commit_hashes: List of commit hashes
    :param parallelise: parallelise
    """
    already_cached = set(commits.keys())
    worklist = set(commit_hashes) - already_cached

    if len(worklist) == 0:
        return

    print('Caching %d/%d commits. This may take a while...' % (len(worklist), len(commit_hashes)))
    sys.stdout.flush()

    done = 0
    for chunk in chunks(list(worklist), 1000):
        sys.stdout.write('\r  %d/%d commits' % (done, len(worklist)))
        sys.stdout.flush()
        if parallelise:
            p = Pool(cpu_count())
            result = p.map(commit_from_commit_hash, chunk)
            p.close()
            p.join()
        else:
            result = map(commit_from_commit_hash, chunk)
        done += len(chunk)
        result = dict(result)
        inject_commits(result)
    print(colored(' [done]', 'green'))


def inject_commits(commit_dict):
    for key, val in commit_dict.items():
        commits[key] = val


def get_date_selector(selector):
    # Date selector "Stack Release Date"
    if selector == 'SRD':
        date_selector = lambda x: patch_stack_definition.get_stack_of_commit(x).stack_release_date
    # Date selector "Commit Date"
    elif selector == 'CD':
        date_selector = lambda x: get_commit(x).commit_date
    else:
        raise NotImplementedError('Unknown date selector: ' % selector)
    return date_selector


patch_stack_definition = PatchStackDefinition.parse_definition_file(config.patch_stack_definition)

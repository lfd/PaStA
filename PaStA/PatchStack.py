"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import csv
import os
import re

from termcolor import colored

from .Util import *


class VersionPoint:
    def __init__(self, commit, version, release_date):
        self.commit = commit
        self.version = version
        self.release_date = parse_date_ymd(release_date)


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
    def parse_definition_file(config):
        """
        Parses the patch stack definition file
        :param config: PaStA configuration
        :return: PatchStackDefinition
        """
        csv.register_dialect('patchstack', delimiter=' ', quoting=csv.QUOTE_NONE)
        repo = config.repo

        sys.stdout.write('Parsing patch stack definition...')

        with open(config.f_patch_stack_definition) as f:
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

                stack_hashes_location = os.path.join(config.d_stack_hashes,
                                                     stack.version)

                # check if stack hashes are existent. If not, create them
                if os.path.isfile(stack_hashes_location):
                    commit_hashes = load_commit_hashes(stack_hashes_location)
                else:
                    print('Calculating missing stack hashes for %s' %
                          stack.commit)
                    commit_hashes = repo.get_commits_on_stack(base.commit,
                                                              stack.commit)
                    persist_commit_hashes(stack_hashes_location, commit_hashes)

                this_group.append(PatchStack(base, stack, commit_hashes))

            patch_stack_groups.append((group_name, this_group))

        # check if upstream commit hashes are existent. If not, create them
        upstream = None
        if (os.path.isfile(config.f_upstream_hashes)):
            upstream = load_commit_hashes(config.f_upstream_hashes)

            # check if upstream range in the config file is in sync
            upstream_range = tuple(upstream.pop(0).split(' '))
            if upstream_range != config.upstream_range:
                print('Upstream range changed. Recalculating.')
                upstream = None

        if not upstream:
            print('Calculating missing upstream commit hashes')
            upstream = repo.get_commithash_range(config.upstream_range)
            persist_commit_hashes(config.f_upstream_hashes,
                                  [' '.join(config.upstream_range)] + upstream)

        if config.upstream_blacklist:
            blacklist = load_commit_hashes(config.upstream_blacklist, ordered=False)
            # filter blacklistes commit hashes
            upstream = [x for x in upstream if x not in blacklist]

        # Create patch stack list
        retval = PatchStackDefinition(patch_stack_groups, upstream)
        print(colored(' [done]', 'green'))

        return retval

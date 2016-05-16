import csv
from datetime import datetime
from multiprocessing import Pool, cpu_count
import os
import re
import sys
from termcolor import colored

from PaStA import config, repo

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
        # Well things are crappy. For decades, encoding has been a real problem
        # Git commits in the linux kernel are messy and sometimes have non-valid encoding
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
    DIFF_SELECTOR_REGEX = re.compile(r'^[-\+@]')

    # The two-line unified diff headers
    FILE_SEPARATOR_MINUS_REGEX = re.compile(r'^--- (.+)$')
    FILE_SEPARATOR_PLUS_REGEX = re.compile(r'^\+\+\+ (.+)$')

    # Exclude '--cc' diffs
    EXCLUDE_CC_REGEX = re.compile(r'^diff --cc (.+)$')

    # Hunks inside a file
    HUNK_REGEX = re.compile(r'^@@ -([0-9]+),?([0-9]+)? \+([0-9]+),?([0-9]+)? @@ ?(.*)$')
    DIFF_REGEX = re.compile(r'^[\+-](.*)$')

    def __init__(self, commit_hash):

        self._commit_hash = commit_hash
        commit = repo[commit_hash]

        message = commit.message
        # Is a revert message?
        self._is_revert = bool(Commit.REVERT_REGEX.search(message))
        # Split by linebreaks and filter empty lines
        self._message = list(filter(None, message.splitlines()))
        # Filter signed-off-by lines
        self._message = list(filter(lambda x: not Commit.SIGN_OFF_REGEX.match(x),
                                   self.message))

        # Respect timezone offsets?
        self._author_date = datetime.fromtimestamp(commit.author.time)
        self._commit_date = datetime.fromtimestamp(commit.commit_time)

        self._author = commit.author.name
        self._author_email = commit.author.email

        tmp = Commit.COMMIT_HASH_LOCATION.match(commit_hash)
        commit_hash_location = '%s/%s/%s' % (tmp.group(1), tmp.group(2), commit_hash)
        diff = file_to_string(os.path.join(config.diffs_location, commit_hash_location))
        self._diff_lines, self._diff = Commit._parse_diff(diff)

        self._affected = set()
        for i, j in self.diff.keys():
            # The [2:] will strip a/ and b/
            if '/dev/null' not in i:
                self._affected.add(i[2:])
            if '/dev/null' not in j:
                self._affected.add(j[2:])

    @property
    def commit_hash(self):
        return self._commit_hash

    @property
    def is_revert(self):
        return self._is_revert

    @property
    def diff_lines(self):
        return self._diff_lines

    @property
    def diff(self):
        return self._diff

    @property
    def message(self):
        return self._message

    @property
    def subject(self):
        return self._message[0]

    @property
    def author_date(self):
        return self._author_date

    @property
    def commit_date(self):
        return self._commit_date

    @property
    def author(self):
        return self._author

    @property
    def author_email(self):
        return self._author_email

    @property
    def affected(self):
        return self._affected

    @staticmethod
    def _parse_diff(diff):
        # Split by linebreaks and filter empty lines
        # Only split at \n and not at \r
        diff = list(filter(None, diff.split('\n')))

        # diff length ratio
        # Filter parts of interest
        lines_of_interest = list(filter(lambda x: Commit.DIFF_SELECTOR_REGEX.match(x), diff))
        diff_lines = sum(map(len, lines_of_interest))

        # Check if we understand the diff format
        if diff and Commit.EXCLUDE_CC_REGEX.match(diff[0]):
            return 0, {}

        retval = {}
        while len(diff):
            # Consume till the first occurence of '--- '
            while len(diff):
                minus = diff.pop(0)
                if Commit.FILE_SEPARATOR_MINUS_REGEX.match(minus):
                    break
            if len(diff) == 0:
                break
            minus = Commit.FILE_SEPARATOR_MINUS_REGEX.match(minus).group(1)
            plus = Commit.FILE_SEPARATOR_PLUS_REGEX.match(diff.pop(0)).group(1)

            diff_index = minus, plus
            if diff_index not in retval:
                retval[diff_index] = {}

            while len(diff) and Commit.HUNK_REGEX.match(diff[0]):
                hunk = Commit.HUNK_REGEX.match(diff.pop(0))

                # l_start = int(hunk.group(1))
                l_lines = 1
                if hunk.group(2):
                    l_lines = int(hunk.group(2))

                # r_start = int(hunk.group(3))
                r_lines = 1
                if hunk.group(4):
                    r_lines = int(hunk.group(4))

                hunktitle = hunk.group(5)

                del_cntr = 0
                add_cntr = 0
                hunk_changes = [], []  # [removed], [inserted]
                while not (del_cntr == l_lines and add_cntr == r_lines):
                    line = diff.pop(0)
                    if line[0] == '+':
                        hunk_changes[1].append(line[1:])
                        add_cntr += 1
                    elif line[0] == '-':
                        hunk_changes[0].append(line[1:])
                        del_cntr += 1
                    elif line[0] != '\\':  # '\\ No new line... statements
                        add_cntr += 1
                        del_cntr += 1

                hunk_changes = (list(filter(None, hunk_changes[0])), \
                                list(filter(None, hunk_changes[1])))

                if hunktitle not in retval[diff_index]:
                    retval[diff_index][hunktitle] = [], []
                retval[diff_index][hunktitle] = (retval[diff_index][hunktitle][0] + hunk_changes[0], \
                                                 retval[diff_index][hunktitle][1] + hunk_changes[1])

        return diff_lines, retval


class VersionPoint:
    def __init__(self, commit, version, release_date):
        self.commit = commit
        self.version = version
        self.release_date = datetime.strptime(release_date, '%Y-%m-%d')


class PatchStack:
    def __init__(self, base, stack):
        self._base = base
        self._stack = stack

        # Commit hashes of the patch stack
        self._commit_hashes = get_commits_from_file(os.path.join(config.stack_hashes, stack.version))

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
        csv_groups.append((header, content))

        patch_stack_groups = []
        for group_name, csv_list in csv_groups:
            reader = csv.DictReader(csv_list, dialect='patchstack')
            this_group = []
            for row in reader:
                base = VersionPoint(row['BaseCommit'],
                                    row['BaseVersion'],
                                    row['BaseReleaseDate'])

                stack = VersionPoint(row['BranchName'],
                                     row['StackVersion'],
                                     row['StackReleaseDate'])

                this_group.append(PatchStack(base, stack))

            patch_stack_groups.append((group_name, this_group))

        upstream = get_commits_from_file(os.path.join(config.stack_hashes, 'upstream'))
        blacklist = get_commits_from_file(config.upstream_blacklist, ordered=False)
        upstream = [x for x in upstream if x not in blacklist]

        # Create patch stack list
        retval = PatchStackDefinition(patch_stack_groups, upstream)
        print(colored(' [done]', 'green'))

        return retval


patch_stack_definition = PatchStackDefinition.parse_definition_file(config.patch_stack_definition)


def get_commit(commit_hash):
    # If commit is already present, return it
    if commit_hash in commits:
        return commits[commit_hash]

    # If it is not present, load it
    commits[commit_hash] = Commit(commit_hash)
    return commits[commit_hash]


def cache_commit_hashes(commit_hashes, parallelise=True):
    sys.stdout.write('Caching %d commits. This may take a while...' % len(commit_hashes))
    sys.stdout.flush()

    if parallelise:
        p = Pool(cpu_count())
        result = p.map(Commit, commit_hashes)
        p.close()
        p.join()
    else:
        result = list(map(Commit, commit_hashes))

    # Fill cache
    for commit_hash, commit in zip(commit_hashes, result):
        commits[commit_hash] = commit

    print(colored(' [done]', 'green'))


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

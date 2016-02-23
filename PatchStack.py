import csv
from datetime import datetime
from math import ceil
from multiprocessing import Pool, cpu_count
import re
from termcolor import colored

from config import *


DATE_LOCATION = LOG_LOCATION + '/' + 'dates/'
AUTHOR_EMAIL_LOCATION = LOG_LOCATION + '/' + 'author_emails/'
DIFFS_LOCATION = LOG_LOCATION + '/' + 'diffs/'
MESSAGES_LOCATION = LOG_LOCATION + '/' + 'messages/'

commits = {}


class Commit:
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

        message = file_to_string(MESSAGES_LOCATION + commit_hash)
        diff = file_to_string(DIFFS_LOCATION + commit_hash)
        date = file_to_string(DATE_LOCATION + commit_hash)
        author_email = file_to_string(AUTHOR_EMAIL_LOCATION + commit_hash)

        self.commit_hash = commit_hash

        self. is_revert = bool(Commit.REVERT_REGEX.search(message))

        # Split by linebreaks and filter empty lines
        self.message = list(filter(None, message.splitlines()))
        # Filter signed-off-by lines
        self.message = list(filter(lambda x: not Commit.SIGN_OFF_REGEX.match(x),
                                   self.message))

        self.diff_length, self.diff = Commit._parse_diff(diff)

        self.affected = set()
        for i, j in self.diff.keys():
            # The [2:] will strip a/ and b/
            if '/dev/null' not in i:
                self.affected.add(i[2:])
            if '/dev/null' not in j:
                self.affected.add(j[2:])

        date = date.splitlines()

        self.author_date = datetime.fromtimestamp(int(date[0]))
        self.commit_date = datetime.fromtimestamp(int(date[1]))

        self.author_email = author_email

    @staticmethod
    def _parse_diff(diff):
        # Split by linebreaks and filter empty lines
        diff = list(filter(None, diff.splitlines()))

        # diff length ratio
        # Filter parts of interest
        lines_of_interest = list(filter(lambda x: Commit.DIFF_SELECTOR_REGEX.match(x), diff))
        diff_length = sum(map(len, lines_of_interest))

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
                hunk_changes = [], []  # [removed], [added]
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

        return diff_length, retval


class VersionPoint:
    def __init__(self, commit, version, release_date):
        self.commit = commit
        self.version = version
        self.release_date = release_date


class PatchStack:
    def __init__(self, base, stack):
        self._base = base
        self._stack = stack

        # Commit hashes of the patch stack
        self._commit_hashes = file_to_string(STACK_HASHES_LOCATION + str(stack.version),
                                             must_exist=True).splitlines()

    @property
    def commit_hashes(self):
        """
        :return: A copy of the commit hashes list
        """
        return set(self._commit_hashes)

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


class PatchStackList:
    def __init__(self, patch_stack_groups):
        self.patch_stack_groups = patch_stack_groups

        self.all_commit_hashes = set()
        for i in self:
            self.all_commit_hashes |= i.commit_hashes

    def get_all_commit_hashes(self):
        """
        :return: Returns all commit hashes of all patch stacks
        """
        return self.all_commit_hashes

    def get_stack_of_commit(self, commit_hash):
        """
        :param commit_hash: Commit hash
        :return: Returns the patch stack that contains commit hash or None
        """
        for i in self:
            if commit_hash in i.commit_hashes:
                return i
        return None

    def iter_groups(self):
        for i in self.patch_stack_groups:
            yield i

    def __contains__(self, item):
        return item in self.all_commit_hashes

    def __iter__(self):
        for foo, patch_stack_group in self.patch_stack_groups:
            for patch_stack in patch_stack_group:
                yield patch_stack


def get_next_release_date(repo, commit_hash):
    description = repo.git.describe('--contains', commit_hash)
    description = description.split('~')[0]
    # The -1 will suppress GPG signatures
    timestamp = repo.git.show('--pretty=format:%ct', '-1', '--no-patch', '--quiet', description)
    timestamp = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
    return timestamp


def get_commit_hashes(repo, start, end):
    """
    :param repo: git repository
    :param start: Start commit
    :param end: End commit
    :return: Returns a set of all commit hashes between a certain range
    """
    hashes = repo.git.log('--pretty=format:%H', start + '...' + end)
    hashes = hashes.splitlines()
    return set(hashes)


def parse_patch_stack_definition(definition_filename):

    csv.register_dialect('patchstack', delimiter=' ', quoting=csv.QUOTE_NONE)
    HEADER_NAME_REGEX = re.compile(r'## (.*)')

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
            header = HEADER_NAME_REGEX.match(line).group(1)
            content = [csv_header]
        elif line.startswith('#'):  # skip comments
            continue
        else:
            content.append(line)

    # Add last group
    csv_groups.append((header, content))

    retval = []
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

        retval.append((group_name, this_group))

    # Create patch stack list
    retval = PatchStackList(retval)
    print(colored(' [done]', 'green'))

    return retval


def get_commit(commit_hash):
    if commit_hash in commits:
        return commits[commit_hash]

    commit = Commit(commit_hash)

    commits[commit_hash] = commit
    return commits[commit_hash]


def cache_commit_hashes(commit_hashes, parallelize=False):
    num_cpus = cpu_count()
    num_commit_hashes = len(commit_hashes)

    sys.stdout.write('Caching ' + str(len(commit_hashes)) +
                     ' commits. This may take a while...')
    sys.stdout.flush()

    if parallelize and num_commit_hashes > 5*num_cpus:
        chunksize = ceil(num_commit_hashes / num_cpus)
        p = Pool(num_cpus)
        p.map(get_commit, commit_hashes, chunksize=chunksize)
        p.close()
        p.join()
    else:
        list(map(get_commit, commit_hashes))

    print(colored(' [done]', 'green'))


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

import csv
from datetime import datetime
from distutils.version import LooseVersion
import functools
from math import ceil
from multiprocessing import Pool, cpu_count
import re
import sys
from termcolor import colored

from config import *
from Tools import file_to_string


DATE_LOCATION = LOG_LOCATION + '/' + 'dates/'
AUTHOR_EMAIL_LOCATION = LOG_LOCATION + '/' + 'author_emails/'
DIFFS_LOCATION = LOG_LOCATION + '/' + 'diffs/'
MESSAGES_LOCATION = LOG_LOCATION + '/' + 'messages/'

commits = {}


class StringVersion:
    """
    Parse a version string like "rt34"
    """

    regex = re.compile('([a-zA-Z]+)([0-9]+)')

    def __init__(self, version_string=''):
        self.string = ''
        self.version = -1

        if not version_string:
            return

        if not self.regex.match(version_string):
            raise Exception('VersionString does not mach: ' + version_string)

        res = self.regex.search(version_string)
        self.string = res.group(1)
        self.version = int(res.group(2))

    def __lt__(self, other):
        # if self.string is empty, then we are newer than the other one
        if not self.string and not not other.string:
            return False
        elif not other.string and not not self.string:
            return True

        # if both version strings are defined, then they must equal
        if self.string != other.string:
            raise Exception('Unable to compare ' + str(self) + ' with ' + str(other))

        return self.version < other.version

    def __str__(self):
        if len(self.string) or self.version != -1:
            return '-' + self.string + str(self.version)
        return ''


class KernelVersion:
    """ Kernel Version

    This class represents a kernel version with a version nomenclature like

    3.12.14.15-rc4-extraversion3

    and is able to compare versions of the class
    """

    versionDelimiter = re.compile('\.|\-')

    def __init__(self, version_string):
        self.versionString = version_string
        self.version = []
        self.rc = StringVersion()
        self.extra = StringVersion()

        # Split array into version numbers, RC and Extraversion
        parts = self.versionDelimiter.split(version_string)

        # Get versions
        while len(parts):
            if parts[0].isdigit():
                self.version.append(parts.pop(0))
            else:
                break

        # Remove trailing '.0's'
        while self.version[-1] == 0:
            self.version.pop()

        # Get optional RC version
        if len(parts) and re.compile('^rc[0-9]+$').match(parts[0]):
            self.rc = StringVersion(parts.pop(0))

        # Get optional Extraversion
        if len(parts):
            self.extra = StringVersion(parts.pop(0))

        # This should be the end now
        if len(parts):
            raise Exception('Unable to parse version string: ' + version_string)

    def base_string(self, num=-1):
        """
        Returns the shortest possible version string of the base version (3.12.0-rc4-rt5 -> 3.12)

        :param num: Number of versionnumbers (e.g. KernelVersion('1.2.3.4').base_string(2) returns '1.2'
        :return: Base string
        """
        if num == -1:
            return ".".join(map(str, self.version))
        else:
            return ".".join(map(str, self.version[0:num]))

    def base_version_equals(self, other, num):
        """
        :param other: Other KernelVersion to compare against
        :param num: Number of subversions to be equal
        :return: True or false

        Examples:
        KernelVersion('3.12.0-rc4-rt5').baseVersionEquals(KernelVersion('3.12'), 3) = true ( 3.12 is the same as 3.12.0)
        KernelVersion('3.12.0-rc4-rt5').baseVersionEquals(KernelVersion('3.12.1'), 3) = false
        """

        left = self.version[0:num]
        right = other.version[0:num]

        # Fillup trailing zeros up to num. This is necessary, as we want to be able to compare versions like
        #   3.12.0     , 3
        #   3.12.0.0.1 , 3
        while len(left) != num:
            left.append(0)

        while len(right) != num:
            right.append(0)

        return left == right

    def __lt__(self, other):
        """
        :param other: KernelVersion to compare against
        :return: Returns True, if the left hand version is an older version
        """
        l = LooseVersion(self.base_string())
        r = LooseVersion(other.base_string())

        if l < r:
            return True
        elif l > r:
            return False

        # Version numbers equal so far. Check RC String
        # A version without a RC-String is the newer one
        if self.rc < other.rc:
            return True
        elif other.rc < self.rc:
            return False

        # We do have the same RC Version. Now check the extraversion
        # The one having an extraversion is considered to be the newer one
        return self.extra < other.extra

    def __str__(self):
        """
        :return: Minimum possible version string
        """
        return self.base_string() + str(self.rc) + str(self.extra)

    def __repr__(self):
        return str(self)


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
    def __init__(self, repo, base, patch):
        self.base = base
        self.patch = patch
        self.patch_version = KernelVersion(patch.version)

        # get commithashes of the patch stack
        self.commit_hashes = get_commit_hashes(repo, base.commit, patch.commit)

    def base_release_date(self):
        return self.base.release_date

    def patch_release_date(self):
        return self.patch.release_date

    def branch_name(self):
        return self.patch.commit

    def num_commits(self):
        return len(self.commit_hashes)

    def __lt__(self, other):
        return self.patch_version < other.patch_version

    def __repr__(self):
        return self.patch.version + ' (' + str(self.num_commits()) + ')'


class PatchStackList(list):
    def __init__(self, *args):
        list.__init__(self, *args)

    def get_all_commit_hashes(self):
        """
        :return: Returns all commit hashes of all patch stacks
        """
        retval = []
        for i in self:
            retval += i.commit_hashes
        return set(retval)

    def get_stack_of_commit(self, commit_hash):
        """
        :param commit_hash: Commit hash
        :return: Returns the patch stack that contains commit hash or None
        """
        for i in self:
            if commit_hash in i.commit_hashes:
                return i
        return None

    def __contains__(self, commit_hash):
        """
        :param commit_hash: Commit hash
        :return: Returns true if commit_hash is in one of the patch stacks
        """
        for i in self:
            if commit_hash in i.commit_hashes:
                return True
        return False


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


def __patch_stack_helper(repo, base_patch):
    sys.stdout.write('\rLoading ' + base_patch[1].version + '...')
    sys.stdout.flush()
    return PatchStack(repo, *base_patch)


def parse_patch_stack_definition(repo, definition_filename):

    retval = []
    csv.register_dialect('patchstack', delimiter=' ', quoting=csv.QUOTE_NONE)

    with open(definition_filename) as f:
        reader = csv.DictReader(filter(lambda row: row[0] != '#', f),  # Skip lines beginning with #
                                dialect='patchstack')
        for row in reader:
            base = VersionPoint(row['BaseCommit'],
                                row['BaseVersion'],
                                row['BaseReleaseDate'])

            patch = VersionPoint(row['BranchName'],
                                 row['PatchVersion'],
                                 row['PatchReleaseDate'])

            retval.append((base, patch))

    # Map tuple of (base, patch) to PatchStack
    pool = Pool(cpu_count())
    retval = PatchStackList(pool.map(functools.partial(__patch_stack_helper, repo), retval))
    pool.close()
    pool.join()
    print(colored(' [done]', 'green'))

    # sort by patch version number
    retval.sort()
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

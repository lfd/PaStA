import csv
from datetime import datetime
from distutils.version import LooseVersion
import functools
from multiprocessing import Pool, cpu_count
import re
import sys
from termcolor import colored

from Tools import file_to_string

AFFECTED_FILES_LOCATION = './log/affected_files/'
AUTHOR_DATE_LOCATION = './log/author_dates/'
AUTHOR_EMAIL_LOCATION = './log/author_emails/'
DIFFS_LOCATION = './log/diffs/'
MESSAGES_LOCATION = './log/messages/'

DIFF_REGEX = re.compile('^[ \t]*[-\+]')

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

    def __lt__(self, other):
        return self.patch_version < other.patch_version

    def num_commits(self):
        return len(self.commit_hashes)

    def __repr__(self):
        return self.patch.version + ' (' + str(self.num_commits()) + ')'


class PatchStackList(list):
    def __init__(self, *args):
        list.__init__(self, *args)

    def get_all_commit_hashes(self):
        retval = []
        for i in self:
            retval += i.commit_hashes
        return retval

    def get_stack_of_commit(self, commit_hash):
        for i in self:
            if commit_hash in i.commit_hashes:
                return i

        return None


class TransitiveKeyList:
    def __init__(self):
        self.forward_lookup = {}
        self.transitive_list = []

    def optimize(self):

        # Get optimized list
        filtered_list = list(filter(None, self.transitive_list))

        # Check if optimization is necessary
        if len(self.transitive_list) != len(filtered_list):
            # Reset lookup table
            self.forward_lookup = {}

            # Filter orphaned elements
            self.transitive_list = filtered_list

            # Recreate the forward lookup dictionary
            for i, keylist in enumerate(self.transitive_list):
                for key in keylist:
                    self.forward_lookup[key] = i

    def is_related(self, key1, key2):
        if key1 in self.forward_lookup and key2 in self.forward_lookup:
            return self.forward_lookup[key1] == self.forward_lookup[key2]

        return False

    def insert(self, key1, key2):
        index1 = key1 in self.forward_lookup
        index2 = key2 in self.forward_lookup

        if not index1 and not index2:
            self.transitive_list.append([key1, key2])
            index = len(self.transitive_list) - 1
            self.forward_lookup[key1] = index
            self.forward_lookup[key2] = index
        elif index1 and index2:
            # Get indices
            index1 = self.forward_lookup[key1]
            index2 = self.forward_lookup[key2]

            # if indices equal, then we have nothing to do
            if index1 != index2:
                # Merge lists
                self.transitive_list[index1] += self.transitive_list[index2]
                # Remove orphaned list
                self.transitive_list[index2] = []

                for i in self.transitive_list[index1]:
                    self.forward_lookup[i] = index1
        elif index1:
            index = self.forward_lookup[key1]
            self.transitive_list[index].append(key2)
            self.forward_lookup[key2] = index
        else:
            index = self.forward_lookup[key2]
            self.transitive_list[index].append(key1)
            self.forward_lookup[key1] = index

    def merge(self, other):
        for i in other.transitive_list:
            base = i[0]
            for j in i[1:]:
                self.insert(base, j)
        self.optimize()

    def to_file(self, filename):
        with open(filename, 'w') as f:
            f.write(str(self))
            f.close()

    def __iter__(self):
        self.optimize()
        for i in self.transitive_list:
            yield i

    def __str__(self):
        return '\n'.join(
                map(lambda x: ' '.join(map(str, x)),
                    filter(None, self.transitive_list)))


def transitive_key_list_from_file(filename):
    retval = TransitiveKeyList()

    content = file_to_string(filename, must_exist=False)
    if content is not None and len(content):
        # split by linebreak
        content = list(filter(None, content.split('\n')))
        for i in content:
            # split eache line by whitespace
            commit_hashes = i.split(' ')
            if len(commit_hashes) < 2:
                raise ValueError('Invalid line')

            base = commit_hashes[0]
            for commit_hash in commit_hashes[1:]:
                retval.insert(base, commit_hash)

    retval.optimize()
    return retval


def get_date_of_commit(repo, commit):
    """
    :param repo: Git Repository
    :param commit: Commit Tag (e.g. v4.3 or SHA hash)
    :return: Author Date in format "YYYY-MM-DD"
    """
    return repo.git.log('--pretty=format:%ad', '--date=short', '-1', commit)


def get_commit_hashes(repo, start, end):
    hashes = repo.git.log('--pretty=format:%H', start + '...' + end)
    hashes = hashes.split('\n')
    return hashes


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

    # Load commit message
    message = file_to_string(MESSAGES_LOCATION + commit_hash)

    # Load commit diff
    diff = file_to_string(DIFFS_LOCATION + commit_hash)
    diff = diff.split('\n')
    # only respect changes
    diff = list(filter(lambda x: DIFF_REGEX.match(x), diff))

    # Load affected files
    affected = file_to_string(AFFECTED_FILES_LOCATION + commit_hash)
    affected = list(filter(None, affected.split('\n')))
    affected.sort()

    # Load author date
    author_date = file_to_string(AUTHOR_DATE_LOCATION + commit_hash)
    author_date = datetime.fromtimestamp(int(author_date))

    # Load author email
    author_email = file_to_string(AUTHOR_EMAIL_LOCATION + commit_hash)

    commits[commit_hash] = (message, diff, affected, author_date, author_email)
    return commits[commit_hash]


def cache_commit_hashes(commit_hashes):
    sys.stdout.write('Caching ' + str(len(commit_hashes)) +
                     ' commits. This may take a while...')
    sys.stdout.flush()
    for commit_hash in commit_hashes:
        get_commit(commit_hash)
    print(colored(' [done]', 'green'))

#!/usr/bin/env python

from distutils.version import LooseVersion
from git import Repo
import re

BRANCH_PREFIX = 'analysis-'
BASE_PREFIX = 'v'
REPO_LOCATION = './linux/'

GNUPLOT_PREFIX = './plots/'
COMMITCOUNT_PREFIX = 'commitcount-'
RT_VERSION_DICT = 'resources/releaseDateList.dat'

class StringVersion:
    """
    Parse a version string like "rt34"
    """

    regex = re.compile('([a-zA-Z]+)([0-9]+)')

    def __init__(self, version_string = ''):
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

    def base_string(self, num = -1):
        """ Returns the shortest possible version string of the base version (3.12.0-rc4-rt5 -> 3.12) """
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


class VersionPoint:
    def __init__(self, commit, version, release_date):
        self.commit = commit
        self.version = version
        self.release_date = release_date


class PatchStack:
    def __init__(self, repo, branch_name, base, patch):
        self.branch_name = branch_name
        self.base = base
        self.patch = patch
        self.kernel_version = KernelVersion(patch.version)

        # get number of commits between baseversion and rtversion
        c = repo.git.log('--pretty=format:%s', base.commit + '...' + patch.commit)
        self.commitlog = c.split('\n')

    def __lt__(self, other):
        return self.kernel_version < other.kernel_version

    def num_commits(self):
        return len(self.commitlog)

    def __repr__(self):
        return self.patch.version + ' (' + str(self.num_commits()) + ')'


def file2dict(filename):
    d = {}
    with open(filename) as f:
        for line in f:
            (key, val) = line.split()
            d[key] = val
    return d


def get_date_of_commit(repo, commit):
    """
    :param repo: Git Repository
    :param commit: Commit Tag (e.g. v4.3 or SHA hash)
    :return: Author Date in format "YYYY-MM-DD"
    """
    return repo.git.log('--pretty=format:%ad', '--date=short', '-1', commit)


def analyse_num_commits(patch_stack_list):

    # Create data file
    cur_version = KernelVersion('0.1')
    xtics = []
    data = {}

    for i in patch_stack_list:

        if i.kernel_version.base_version_equals(KernelVersion('2.6'), 2):
            num_major = 3
        else:
            num_major = 2

        if not i.kernel_version.base_version_equals(cur_version, num_major):
            xtics.append((i.patch.version, "'" + i.patch.release_date + "'"))
            cur_version = i.kernel_version
            data[cur_version.base_string()] = []

        data[cur_version.base_string()].append('"' + \
                                               i.kernel_version.base_string(2) + '" ' + \
                                               '"' + i.base.version + '" ' + \
                                               i.base.release_date + ' ' + \
                                               '"' + i.patch.version + '" ' + \
                                               i.patch.release_date + ' ' + \
                                               str(i.num_commits()))

    for key, value in data.items():
        f = open(GNUPLOT_PREFIX + COMMITCOUNT_PREFIX + key, 'w')
        f.write('# basbaseVersion\t baseVersion\t baseReleaseDate\t patchVersion\t patchReleaseDate\t numCommits\n')
        sum = "\n".join(value) + '\n'
        f.write(sum)
        f.close()

    # set special xtics
    print("set xtics (" +
          ", ".join(map(lambda x: '"' + x[0] + '" ' + str(x[1]), xtics)) +
          ")\n")

# Main
repo = Repo(REPO_LOCATION)
patch_stack_list = []
rt_version_dict = file2dict(RT_VERSION_DICT)

for head in repo.heads:
    # Skip if branch name does not start with analysis-
    if not head.name.startswith(BRANCH_PREFIX):
        continue

    # get rtversion and baseversion
    branch_name = head.name
    patch_version = re.compile(BRANCH_PREFIX + '(.*)').search(branch_name).group(1)
    base_version = re.compile('(.*)-rt[0-9]*').search(patch_version).group(1)

    # special treatments...
    if base_version == '3.12.0':
        base_version = '3.12'
    if base_version == '3.14.0':
        base_version = '3.14'

    # set base Tag
    base_tag = BASE_PREFIX + base_version

    # be a bit verbose
    print('Working on ' + patch_version + ' <- ' + base_version)

    base = VersionPoint(base_tag, base_version, get_date_of_commit(repo, base_tag))
    patch = VersionPoint(branch_name, patch_version, rt_version_dict.get(patch_version))
    p = PatchStack(repo, branch_name, base, patch)
    patch_stack_list.append(p)

# Sort the stack by patchversion
patch_stack_list.sort()

# Run analyse_num_commits on the patchstack
analyse_num_commits(patch_stack_list)

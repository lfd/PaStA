#!/usr/bin/env python

from distutils.version import LooseVersion
from git import Repo
import re
from subprocess import call

BRANCH_PREFIX = 'analysis-'
BASE_PREFIX = 'v'
REPO_LOCATION = './linux/'

GNUPLOT_PREFIX = './plots/'
DATA_NUM_COMMITS = 'num_commits.dat'
PLOT_NUM_COMMITS = 'num_commits.gnuplot'


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
        self.rc = ''
        self.extra = ''

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
            self.rc = parts.pop(0)

        # Get optional Extraversion
        if len(parts):
            self.extra = parts.pop(0)

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
        if not self.rc and not not other.rc:
            return False
        elif not other.rc and not not self.rc:
            return True
        # both have 'some' version. Compare it.
        if self.rc < other.rc:
            return True
        elif other.rc < self.rc:
            return False

        # We do have the same RC Version. Now check the extraversion
        # The one having an extraversion is considered to be the newer one
        if not self.extra and not not other.extra:
            return True
        elif not other.extra and not not self.extra:
            return False

        # both have 'some' extraversion. Compare it.
        return self.extra < other.extra

    def __str__(self):
        """
        :return: Minimum possible version string
        """
        retval = self.base_string()
        if len(self.rc):
            retval += '-' + self.rc

        if len(self.extra):
            retval += '-' + self.extra

        return retval


class PatchStack:
    def __init__(self, repo, base_version, base_tag, patch_version, branch_name):
        self.base_version = base_version
        self.base_tag = base_tag
        self.patch_version = patch_version
        self.branch_name = branch_name
        self.kernel_version = KernelVersion(patch_version)

        # get number of commits between baseversion and rtversion
        c = repo.git.log('--pretty=format:%s', base_tag + '...' + branch_name)
        self.commitlog = c.split('\n')

    def __lt__(self, other):
        return self.kernel_version < other.kernel_version

    def num_commits(self):
        return len(self.commitlog)

    def __repr__(self):
        return self.patch_version + ' (' + str(self.num_commits()) + ')'


def analyse_num_commits(patch_stack_list):

    # Create data file
    f = open(GNUPLOT_PREFIX + DATA_NUM_COMMITS, 'w')
    f.write('# no    baseVersion     patchVersion     numCommits\n')
    cur_version = KernelVersion('0.1')
    xtics = []

    for (no, i) in enumerate(patch_stack_list):
        no += 1

        if i.kernel_version.base_version_equals(KernelVersion('2.6'), 2):
            num_major = 3
        else:
            num_major = 2

        if not i.kernel_version.base_version_equals(cur_version, num_major):
            xtics.append((i.patch_version, no))
            cur_version = i.kernel_version

        f.write(str(no) +
                ' "' + i.base_version + '" ' +
                '"' + i.patch_version + '" ' +
                str(i.num_commits()) + ' ' +
                '"' + i.kernel_version.base_string(2) + '"' + '\n')

    f.close()

    location = GNUPLOT_PREFIX + PLOT_NUM_COMMITS
    f = open(location, 'w')
    f.write("set title 'PreemptRT: Number of commits'\n"
            "#set terminal postscript eps enhanced color font 'Helvetica,10'\n"
            "#set output 'preemptrt_commitcount.eps'\n"
            "unset xtics\n"
            "set ylabel 'Number of commits'\n"
            "set xlabel 'PreemptRT kernel version'\n"
            "set xtics nomirror rotate by -45\n\n")

    # set special xtics
    f.write("set xtics (" +
            ", ".join(map(lambda x: '"' + x[0] + '" ' + str(x[1]), xtics)) +
            ")\n")

    # final plot call
    f.write("plot \"" + GNUPLOT_PREFIX + DATA_NUM_COMMITS + "\" u 1:4 w points notitle\n")
    f.write("pause -1 'press key to exit'\n")
    f.close()

    # Call gnuplot
    call(["gnuplot", location])

# Main
repo = Repo(REPO_LOCATION)
patch_stack_list = []

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

    p = PatchStack(repo, base_version, base_tag, patch_version, branch_name)
    patch_stack_list.append(p)

# Sort the stack by patchversion
patch_stack_list.sort()

# Run analyse_num_commits on the patchstack
analyse_num_commits(patch_stack_list)

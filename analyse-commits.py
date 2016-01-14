#!/usr/bin/env python

from distutils.version import LooseVersion
from git import Repo
import re
from subprocess import call

branch_prefix = 'analysis-'
base_prefix = 'v'
repo_location = './linux/'

gnuplot_prefix = './plots/'
data_num_commits = 'num_commits.dat'
plot_num_commits = 'num_commits.gnuplot'

class KernelVersion:
    """ Kernel Version

    This class represents a kernel version with a version nomenclature like

    3.12.14.15-rc4-extraversion3

    and is able to compare versions of the class
    """

    versionDelimiter = re.compile('\.|\-')

    def __init__(self, versionString):
        self.versionString = versionString
        self.version = []
        self.rc = ''
        self.extra = ''

        # Split array into version numbers, RC and Extraversion
        parts = self.versionDelimiter.split(versionString)

        # Get versions
        cntr = 0
        for i in parts: # get version numbers
            if i.isdigit():
                self.version.append(int(i))
                cntr += 1
            else:
                break

        # Remove trailing '.0's'
        while (self.version[-1] == 0):
            self.version.pop()

        # Get optional RC version
        if (cntr != len(parts) and re.compile('^rc[0-9]+$').match(parts[cntr])):
            self.rc = parts[cntr]
            cntr += 1

        # Get optional Extraversion
        if (cntr != len(parts)):
            self.extra = parts[cntr]
            cntr += 1

        # This should be the end now
        if (cntr != len(parts)):
            raise Exception('Unable to parse version string: ' + versionString)

    def baseString(self):
        """ Returns the shortest possible version string of the base version (3.12.0-rc4-rt5 -> 3.12) """
        return ".".join(map(str, self.version))

    def baseVersionEquals(self, other, num):
        """
        :param other: Other KernelVersion to compare against
        :param num: Number of subversions to be equal
        :return: True or false

        Examples:
        KernelVersion('3.12.0-rc4-rt5').baseVersionEquals(KernelVersion('3.12'), 3) would be true (as 3.12 is the same as 3.12.0)
        KernelVersion('3.12.0-rc4-rt5').baseVersionEquals(KernelVersion('3.12.1'), 3) would be false
        """

        left = self.version[0:num]
        right = other.version[0:num]

        # Fillup trailing zeros up to num. This is necessary, as we want to be able to compare versions like
        #   3.12.0     , 3
        #   3.12.0.0.1 , 3
        while (len(left) != num ):
            left.append(0)

        while (len(right) != num ):
            right.append(0)

        return left == right

    def __lt__(self, other):
        """
        :param other: KernelVersion to compare against
        :return: Returns True, if the left hand version is an older version
        """
        l = LooseVersion(self.baseString())
        r = LooseVersion(other.baseString())

        if (l < r):
            return True
        elif (l > r):
            return False

        # Version numbers equal so far. Check RC String
        # A version without a RC-String is the newer one
        if (not self.rc and not not other.rc):
            return False
        elif (not other.rc and not not self.rc):
            return True
        # both have 'some' version. Compare it.
        if (self.rc < other.rc):
            return True
        elif (other.rc < self.rc):
            return False

        # We do have the same RC Version. Now check the extraversion
        # The one having an extraversion is considered to be the newer one
        if (not self.extra and not not other.extra):
            return True
        elif (not other.extra and not not self.extra):
            return False

        # both have 'some' extraversion. Compare it.
        return self.extra < other.extra




class PatchStack:
    def __init__(self, repo, baseVersion, baseTag, patchVersion, branchName):
        self.baseVersion = baseVersion
        self.baseTag = baseTag
        self.patchVersion = patchVersion
        self.branchName = branchName
        self.kernelVersion = KernelVersion(patchVersion)

        # get number of commits between baseversion and rtversion
        c = repo.git.log('--pretty=format:%s', baseTag + '...' + branchName)
        self.commitlog = c.split('\n')

    def __lt__(self, other):
        return self.kernelVersion < other.kernelVersion

    def numCommits(self):
        return len(self.commitlog)

    def __repr__(self):
        return self.patchversion + ' (' + str(self.numCommits()) + ')'




def analyseNumCommits(patchStackList):

    # Create data file
    f = open(gnuplot_prefix + data_num_commits, 'w')
    f.write('# no    baseVersion     patchVersion     numCommits\n')
    curVersion = KernelVersion('0.1')
    xtics = []

    for (no,i) in enumerate(patchStackList):
        no += 1

        if i.kernelVersion.baseVersionEquals(KernelVersion('2.6'), 2):
            numMajor = 3
        else:
            numMajor = 2

        if not i.kernelVersion.baseVersionEquals(curVersion, numMajor):
            xtics.append( (i.patchVersion, no) )
            curVersion = i.kernelVersion

        f.write(str(no)
                + ' "' + i.baseVersion + '" '
                + '"' + i.patchVersion + '" '
                + str(i.numCommits()) + '\n')

    f.close()

    location = gnuplot_prefix + plot_num_commits
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
    f.write("plot \"" + gnuplot_prefix + data_num_commits + "\" u 1:4 w points notitle\n")
    f.write("pause -1 'foo'\n")
    f.close()

    # Call gnuplot
    call(["gnuplot", location])

## Main ##
repo = Repo(repo_location)
patchStackList = []

for head in repo.heads:
    # Skip if branch name does not start with analysis-
    if (not head.name.startswith(branch_prefix)):
        continue

    # get rtversion and baseversion
    branchName = head.name
    patchVersion = re.compile(branch_prefix + '(.*)').search(branchName).group(1)
    baseVersion = re.compile('(.*)-rt[0-9]*').search(patchVersion).group(1)

    # special treatments...
    if (baseVersion == '3.12.0'):
        baseVersion = '3.12'
    if (baseVersion == '3.14.0'):
        baseVersion = '3.14'

    # set base Tag
    baseTag = base_prefix + baseVersion

    # be a bit verbose
    print('Working on ' + patchVersion + ' <- ' + baseVersion)

    p = PatchStack(repo, baseVersion, baseTag, patchVersion, branchName)
    patchStackList.append(p)

# Sort the stack by patchversion
patchStackList.sort()

analyseNumCommits(patchStackList)

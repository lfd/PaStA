from distutils.version import LooseVersion
import re


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

    VERSION_DELIMITER = re.compile('\.|\-')
    RC_REGEX = re.compile('^rc[0-9]+$')

    def __init__(self, version_string):
        self.versionString = version_string
        self.version = []
        self.rc = StringVersion()
        self.extra = StringVersion()

        # Split array into version numbers, RC and Extraversion
        parts = self.VERSION_DELIMITER.split(version_string)

        # Get versions
        while len(parts):
            if parts[0].isdigit():
                no = int(parts.pop(0))
                self.version.append(no)
            else:
                break

        # Remove trailing '.0's'
        while len(self.version) > 1 and self.version[-1] == 0:
                self.version.pop()

        if not self.version:
            self.version = [0]

        # Get optional RC version
        if len(parts) and KernelVersion.RC_REGEX.match(parts[0]):
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

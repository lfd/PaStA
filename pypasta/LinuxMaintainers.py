"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019-2020

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import re

from enum import Enum
from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from .Util import load_pkl_and_update

log = getLogger(__name__[-15:])


class Matcher:
    @staticmethod
    def regex_rewrite(regex):
        # A wildcard means that it can be anything but '/'
        regex = regex.replace('*', '([^/]*)')
        # A ? means it can be any character besides '/'
        regex = regex.replace('?', '([^/])')

        # If the regex ends with /, then we can match anything behind the /
        if regex[-1] == '/':
            regex += '.*'

        regex = '^%s$' % regex

        return re.compile(regex)

    def match(self, filename):
        if filename in self.direct_match:
            return True

        for regex in self.wildcards:
            if regex.match(filename):
                return True

        return False

    def __init__(self, files):
        # Walk over files, look for wildcard entries and convert them to proper
        # python regexes
        self.direct_match = list()
        self.wildcards = list()

        for entry in files:
            # If the last character is a wildcard, we need to respect subdirs
            # that could be completed from the wildcard
            if entry[-1] == '*':
                self.wildcards.append(self.regex_rewrite(entry + '/'))

            if '*' in entry or '?' in entry or entry[-1] == '/':
                self.wildcards.append(self.regex_rewrite(entry))
            else:
                self.direct_match.append(entry)


class NMatcher:
    def match(self, filename):
        for expression in self.expressions:
            if expression.match(filename):
                return True

        return False

    def __init__(self, expressions):
        self.expressions = list()

        for expression in expressions:
            while expression[-1] == '*':
                expression = expression[:-1]

            expression = '.*%s.*' % expression
            self.expressions.append(re.compile(expression))


class LinuxSubsystem:
    DESCRIPTOR_REGEX = re.compile(r'([A-Z]):\s*(.*)')
    EMAIL_RAW_REGEX = r'\S+@\S+\.\S+'

    # matches a name and an email in brackets, such as 'John F. Doe <john.f.doe@gmail.com>'
    EMAIL_DEFAULT_REGEX = re.compile('(.*)<(%s)>' % EMAIL_RAW_REGEX)
    # matches two emails in brackets, such as '<john.f.doe@gmail.com> <joedoe@outlook.com>'
    EMAIL_MM_REGEX = re.compile('<(%s)>\\s*<(%s)>' % (EMAIL_RAW_REGEX, EMAIL_RAW_REGEX))
    # matches a name and two emails in brackets, such as 'John F. Doe <john.f.doe@gmail.com> <joedoe@outlook.com>'
    EMAIL_NMM_REGEX = re.compile('(.*)<(%s)>(.*)<(%s)>' % (EMAIL_RAW_REGEX, EMAIL_RAW_REGEX))
    # matches a name followed by an email twice, such as:
    # 'John F. Doe <john.f.doe@gmail.com> Emily Swanson <emily.s@gmail.com>
    EMAIL_NMNM_REGEX = re.compile('(.*)<(%s)>(.*)<(%s)>' % (EMAIL_RAW_REGEX, EMAIL_RAW_REGEX))
    # matches a typical email address such as 'john.doe@gmail.com'
    EMAIL_MAIL_REGEX = re.compile(r'(%s)' % EMAIL_RAW_REGEX)

    class Status(Enum):
        Supported = 'supported'
        Maintained = 'maintained'
        OddFixes = 'odd fixes'
        Obsolete = 'obsolete'
        Orphan = 'orphan'
        Buried = 'buried'

    @staticmethod
    def parse_person(value):
        match = LinuxSubsystem.EMAIL_DEFAULT_REGEX.match(value)
        if match:
            return [(match.group(1).strip(), match.group(2))]

        match = LinuxSubsystem.EMAIL_MM_REGEX.match(value)
        if match:
            return [('', match.group(1)), ('', match.group(2))]

        match = LinuxSubsystem.EMAIL_NMM_REGEX.match(value)
        if match:
            raise NotImplementedError('IMPLEMENT ME %s' % value)

        match = LinuxSubsystem.EMAIL_NMNM_REGEX.match(value)
        if match:
            return [(match.group(1), match.group(2)),
                    (match.group(3), match.group(4))]

        match = LinuxSubsystem.EMAIL_MAIL_REGEX.match(value)
        if match:
            return [('', match.group(1))]

        if '@' not in value:
            return [(value, '')]

        if value == 'vince bridgers <vbridgers2013@gmail.com':
            return [('vince bridgers', 'vbridgers2013@gmail.com')]

        raise RuntimeError('Unable to parse %s' % value)

    def match(self, filename):
        if self.xmatcher.match(filename):
            return False

        if self.matcher.match(filename):
            return True

        if self.nmatcher.match(filename):
            return True

        return False

    def get_maintainers(self):
        return self.list, self.mail + self.person, self.reviewers

    def __init__(self, entry):
        self.description = list()

        self.mail = list()
        self.list = set()
        self.tree = list()
        self.status = list()
        self.person = list()
        self.reviewers = list()
        self.patchwork = list()
        self.webpage = None
        self.bugs = list()
        self.chat = list()

        # Required for filename matching
        self.keywords = list()
        self.files = list()
        self.xfiles = list()
        self.regex_patterns = list()

        while not self.DESCRIPTOR_REGEX.match(entry[0]):
            self.description.append(entry.pop(0))
        self.description = ' / '.join(self.description)

        for line in entry:
            # some nasty cases
            if line.startswith('F\tinclude') or line.startswith('F\tDocument'):
                line = 'F:\t' + line[2:]

            match = self.DESCRIPTOR_REGEX.match(line)
            if not match:
                print('Oo: %s' % line)
                continue
            type, value = match.group(1), match.group(2)

            if type == 'M':
                value = value.lower()
                self.mail += self.parse_person(value)
            elif type == 'L':
                value = value.lower()
                # We have some lists that are no email adresses. Skip them
                if value.startswith('http://'):
                    continue
                ml = self.EMAIL_MAIL_REGEX.findall(value)[0]
                self.list.add(ml)
            elif type == 'S':
                # some nasty cases
                if value == 'Odd Fixes (e.g., new signatures)':
                    value = 'odd fixes'
                elif value == 'Maintained for 2.6.':
                    value = 'maintained'
                elif value == 'Maintained:':
                    value = 'maintained'
                elif value == 'Unmaintained':
                    value = 'orphan'
                elif value.lower() == 'buried alive in reporters':
                    value = 'buried'

                stati = [x.strip().lower() for x in value.split('/')]
                self.status += [LinuxSubsystem.Status(x) for x in stati]
            elif type == 'F':
                self.files.append(value)
            elif type == 'W':
                self.webpage = value
            elif type == 'T':
                self.tree.append(value)
            elif type == 'Q':
                self.patchwork.append(value)
            elif type == 'P':
                value = value.lower()
                self.person += self.parse_person(value)
            elif type == 'X':
                self.xfiles.append(value)
            elif type == 'K':
                self.keywords.append(value)
            elif type == 'N':
                self.regex_patterns.append(value)
            elif type == 'R':
                value = value.lower()
                self.reviewers += self.parse_person(value)
            elif type == 'B':
                self.bugs.append(value)
            elif type == 'C':
                self.chat.append(value)
            else:
                raise RuntimeError('Unknown Maintainer Entry: %s' % line)

        self.matcher = Matcher(self.files)
        self.xmatcher = Matcher(self.xfiles)
        self.nmatcher = NMatcher(self.regex_patterns)


class LinuxMaintainers:
    def get_subsystems_by_files(self, filenames):
        subsystems = set()
        for file in filenames:
            if file.startswith('linux/'):
                file = file[len('linux/'):]
            subsystems |= self.get_subsystems_by_file(file)

        return subsystems

    def get_subsystems_by_file(self, filename):
        subsystems = set()
        for subsystem in self.subsystems.values():
            if subsystem.match(filename):
                subsystems.add(subsystem.description)
        return subsystems

    def get_maintainers(self, subsystem):
        return self.subsystems[subsystem].get_maintainers()

    def __getitem__(self, item):
        return self.subsystems[item]

    def __init__(self, maintainers):
        self.subsystems = dict()

        def add_subsystem(content):
            subsys = LinuxSubsystem(content)
            self.subsystems[subsys.description] = subsys

        # For all versions, we can drop the first ~70 lines
        maintainers = maintainers.splitlines()[70:]

        # We always look for a line that starts with 3C
        while not maintainers[0].startswith('3C'):
            maintainers.pop(0)

        tmp = list()
        for line in maintainers:
            if len(line.strip()) == 0:
                if len(tmp):
                    add_subsystem(tmp)
                tmp = list()
            else:
                tmp.append(line)
        add_subsystem(tmp)

def load_maintainer(repo, revision):
    maintainers = repo.get_blob(revision, 'MAINTAINERS')
    try:
        maintainers = maintainers.decode('utf-8')
    except:
        # older versions use ISO8859
        maintainers = maintainers.decode('iso8859')

    return LinuxMaintainers(maintainers)


def _load_maintainer(revision):
    return revision, load_maintainer(_repo, revision)


def load_maintainers(config, versions):
    def __load_maintainers(ret, config, versions):
        if ret is None:
            ret = dict()

        # Only load what's not yet cached
        versions -= ret.keys()

        if len(versions) == 0:
            return ret, False

        global _repo
        _repo = config.repo
        p = Pool(processes=cpu_count())
        for tag, maintainers in tqdm(p.imap_unordered(_load_maintainer,
                                                      versions),
                                     total=len(versions), desc='MAINTAINERS'):
            ret[tag] = maintainers

        p.close()
        p.join()
        _repo = None

        return ret, True

    log.info('Loading/Updating MAINTAINERS...')
    maintainers_version = load_pkl_and_update(config.f_maintainers_pkl,
                                              __load_maintainers, config,
                                              versions)
    return maintainers_version

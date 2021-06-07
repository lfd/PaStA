"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2019-2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import pygit2
import re

from enum import Enum
from functools import partial
from logging import getLogger
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

from .Util import load_pkl_and_update

log = getLogger(__name__[-15:])


def _prepare_linux(maintainers):
    # For all versions, we can drop the first ~70 lines
    maintainers = maintainers[70:]

    # We always look for a line that starts with 3C
    while not maintainers[0].startswith('3C'):
        maintainers.pop(0)

    return maintainers


def _prepare_qemu(maintainers):
    maintainers_new = list()

    def append_subtopic(topic, subtopic, content):
        nonlocal maintainers_new
        if subtopic:
            maintainers_new.append('%s - %s' % (topic, subtopic))
        else:
            maintainers_new.append('%s' % topic)
        maintainers_new += content + ['']

    while not maintainers[0].startswith('General'):
        maintainers.pop(0)

    # Remove empty lines
    maintainers = list(filter(None, maintainers))

    maintainers = [re.sub('^S: Support$', 'S: Supported', x) for x in maintainers]
    maintainers = [re.sub('Orphan.*', 'Orphan', x, flags=re.IGNORECASE) for x in maintainers]

    topic = None
    subtopic = None
    content = list()
    no = 0
    while no < len(maintainers):
        line = maintainers[no]
        line_next = ''
        if no + 1 < len(maintainers):
            line_next = maintainers[no+1]

        if line_next.startswith('-----'):
            if topic:
                append_subtopic(topic, subtopic, content)
                content = list()
                subtopic = None

            topic = line
            no += 2
            continue

        if line[1] == ':':
            content.append(line)
        else:
            if subtopic:
                append_subtopic(topic, subtopic, content)
                content = list()
            subtopic = line
        no += 1

    # Remove last trailing newline
    maintainers_new.pop()

    return maintainers_new


def _prepare_uboot(maintainers):
    # We always look for a line that starts with ----
    while not maintainers[0].strip().startswith('---'):
        maintainers.pop(0)

    # throw away the --- line, in order to have maintainers start on the
    # first section
    maintainers.pop(0)

    maintainers = [re.sub('Maintainted', 'Maintained', x) for x in maintainers]
    maintainers = [re.sub('Orphan.*', 'Orphan', x, flags=re.IGNORECASE) for x in maintainers]
    # Orphaned sections will often have maintainters 'commented out'. We need to remove
    # them manually to prevent them from appearing in the section name
    maintainers = [x for x in maintainers if not x.strip().startswith('#M:')]

    # In some versions of u-boot, we find a ^F. instead of ^F: . Replace it.
    maintainers = [re.sub('^F\.', 'F:', x) for x in maintainers]

    return maintainers

_prepare_maintainers = {
    'linux': _prepare_linux,
    'qemu': _prepare_qemu,
    'u-boot': _prepare_uboot,
    # we can use the exact same routine as u-boot
    'xen': _prepare_uboot,
}


class Matcher:
    @staticmethod
    def regex_rewrite(regex):
        # A wildcard means that it can be anything but '/'
        regex = regex.replace('*', '([^/]*)')
        # A ? means it can be any character besides '/'
        regex = regex.replace('?', '([^/])')
        # Regexes like abc.[ch] don't need any rewrite rules.

        return regex

    def match(self, filename):
        if filename in self.direct_match:
            return True

        for prefix in self.dir_prefix:
            if filename.startswith(prefix):
                return True

        for regex in self.regexes:
            if regex.match(filename):
                return True

        return False

    def __init__(self, files, tree):
        # Walk over files, look for wildcard entries and convert them to proper
        # python regexes
        self.direct_match = list()
        self.dir_prefix = set()
        self.regexes = set()

        for entry in files:
            contains_regex = any({x in entry for x in {'*', '?', '[', ']'}})
            if not contains_regex and entry[-1] != '/':
                if entry in tree:
                    object = tree[entry]
                    if isinstance(object, pygit2.Blob):
                        self.direct_match.append(entry)
                    elif isinstance(object, pygit2.Tree):
                        self.dir_prefix.add(entry + '/')
                    continue
                else:
                    log.debug('Referenced MAINTAINERS entry not in git tree: %s' % entry)
                    # We can simply ignore an entry that does not even exist
                    continue

            ends_on_slash = entry[-1] == '/'
            if contains_regex:
                entry = self.regex_rewrite(entry)

            if ends_on_slash:
                # Match everything beyond the directory
                entry = '%s.*' % entry

            entry = '^%s$' % entry
            self.regexes.add(re.compile(entry))


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


class Section:
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
        match = Section.EMAIL_DEFAULT_REGEX.match(value)
        if match:
            return [(match.group(1).strip().strip('"'), match.group(2))]

        match = Section.EMAIL_MM_REGEX.match(value)
        if match:
            return [('', match.group(1)), ('', match.group(2))]

        match = Section.EMAIL_NMM_REGEX.match(value)
        if match:
            raise NotImplementedError('IMPLEMENT ME %s' % value)

        match = Section.EMAIL_NMNM_REGEX.match(value)
        if match:
            return [(match.group(1), match.group(2)),
                    (match.group(3), match.group(4))]

        match = Section.EMAIL_MAIL_REGEX.match(value)
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

    def __init__(self, repo, revision, entry):
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
        self.version = list()

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
                self.status += [Section.Status(x) for x in stati]
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
            elif type == 'V':
                self.version.append(value)
            else:
                raise RuntimeError('Unknown Maintainer Entry: %s' % line)

        tree = repo.get_tree(revision)
        self.matcher = Matcher(self.files, tree)
        self.xmatcher = Matcher(self.xfiles, tree)
        self.nmatcher = NMatcher(self.regex_patterns)


class MAINTAINERS:
    def get_sections_by_files(self, filenames):
        sections = set()
        for file in filenames:
            if file.startswith('linux/'):
                file = file[len('linux/'):]
            sections |= self.get_sections_by_file(file)

        return sections

    def get_sections_by_file(self, filename):
        sections = set()
        for section in self.sections.values():
            if section.match(filename):
                sections.add(section.description)
        return sections

    def get_maintainers(self, section):
        return self.sections[section].get_maintainers()

    def __getitem__(self, item):
        return self.sections[item]

    def __init__(self, d_cluster, project_name, repo, revision):
        maintainers = repo.get_blob(revision, 'MAINTAINERS')
        try:
            maintainers = maintainers.decode('utf-8')
        except:
            # older versions use ISO8859
            maintainers = maintainers.decode('iso8859')

        maintainers = maintainers.splitlines()

        if project_name in _prepare_maintainers:
            maintainers = _prepare_maintainers[project_name](maintainers)
        else:
            raise NotImplementedError(
                'No MAINTAINERS implementation for project' % project_name)

        self.sections = dict()

        def add_section(content):
            section = Section(repo, revision, content)
            self.sections[section.description] = section

        tmp = list()
        for line in maintainers:
            if len(line.strip()) == 0:
                if len(tmp):
                    add_section(tmp)
                tmp = list()
            else:
                tmp.append(line)
        add_section(tmp)

        f_maintainers_cluster = os.path.join(d_cluster, '%s.txt' % revision)
        self.cluster = None
        if os.path.exists(f_maintainers_cluster):
            with open(f_maintainers_cluster, 'r') as f:
                cluster = f.read()
            cluster = list(filter(None, cluster.split('\n\n')))
            self.cluster = [set(x.split('\n')) for x in cluster]
        else:
            log.warning('No MAINTAINERS cluster for %s' % revision)


def _load_maintainer(revision, d_cluster, project_name):
    return revision, MAINTAINERS(d_cluster, project_name, _repo, revision)


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
        function = partial(_load_maintainer,
                           d_cluster = config.d_maintainers_cluster,
                           project_name = config.project_name)

        for tag, maintainers in tqdm(p.imap_unordered(function, versions),
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

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re


class Hunk:
    def __init__(self, insertions=None, deletions=None, context=None):
        self._insertions = insertions or []
        self._deletions = deletions or []
        self._context = context or []

    def merge(self, other):
        self._insertions += other.insertions
        self._deletions += other.deletions
        self._context += other.context

    @property
    def deletions(self):
        return self._deletions

    @property
    def insertions(self):
        return self._insertions

    @property
    def context(self):
        return self._context


class Diff:
    DIFF_SELECTOR_REGEX = re.compile(r'^[-\+@]')

    # The two-line unified diff headers
    FILE_SEPARATOR_MINUS_REGEX = re.compile(r'^--- ([^\s]*).*$')
    #r'^--- (?P<filename>[^\t\n]+)(?:\t(?P<timestamp>[^\n]+))?')
    FILE_SEPARATOR_PLUS_REGEX = re.compile(r'^\+\+\+ ([^\s]*).*$')

    # Exclude '--cc' diffs
    EXCLUDE_CC_REGEX = re.compile(r'^diff --cc (.+)$')

    # Hunks inside a file
    HUNK_REGEX = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?\ @@[ ]?(.*)')

    LINE_IDENTIFIER_INSERTION = '+'
    LINE_IDENTIFIER_DELETION = '-'
    LINE_IDENTIFIER_CONTEXT = ' '
    LINE_IDENTIFIER_NEWLINE = '\\'

    def __init__(self, diff):
        # we pop from the list until it is empty. Copy it first, to prevent its
        # deletion
        self.raw = list(diff)
        self.patches = {}
        self.affected = set()

        # Calculate diff_lines
        self.lines = len(list(
            filter(lambda x: Diff.DIFF_SELECTOR_REGEX.match(x), diff)))

        # Check if we understand the diff format
        if diff and Diff.EXCLUDE_CC_REGEX.match(diff[0]):
            return

        while len(diff):
            self.footer = len(diff)

            # Consume till the first occurence of '--- '
            while len(diff):
                minus = diff.pop(0)
                if Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus):
                    break
            if len(diff) == 0:
                break

            self.footer = 0
            minus = Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus).group(1)
            plus = Diff.FILE_SEPARATOR_PLUS_REGEX.match(diff.pop(0)).group(
                1)

            filename = Diff.get_filename(minus, plus)

            while len(diff) and Diff.HUNK_REGEX.match(diff[0]):
                hunk = Diff.HUNK_REGEX.match(diff.pop(0))

                # l_start = int(hunk.group(1))
                l_lines = 1
                if hunk.group(2):
                    l_lines = int(hunk.group(2))

                # r_start = int(hunk.group(3))
                r_lines = 1
                if hunk.group(4):
                    r_lines = int(hunk.group(4))

                hunk_heading = hunk.group(5)

                del_cntr = 0
                add_cntr = 0

                insertions = []
                deletions = []
                context = []

                while not (del_cntr == l_lines and add_cntr == r_lines):
                    line = diff.pop(0)

                    # Assume an empty string to be an invariant newline
                    # (this happens quite often when parsing mails)
                    if line == '':
                        identifier = ' '
                        payload = ''
                    else:
                        identifier = line[0]
                        payload = line[1:]

                    if identifier == Diff.LINE_IDENTIFIER_INSERTION:
                        insertions.append(payload)
                        add_cntr += 1
                    elif identifier == Diff.LINE_IDENTIFIER_DELETION:
                        deletions.append(payload)
                        del_cntr += 1
                    elif identifier == Diff.LINE_IDENTIFIER_CONTEXT:
                        context.append(payload)
                        add_cntr += 1
                        del_cntr += 1
                    elif identifier != Diff.LINE_IDENTIFIER_NEWLINE:  # '\ No new line' statements
                        add_cntr += 1
                        del_cntr += 1

                # remove empty lines
                insertions = list(filter(None, insertions))
                deletions = list(filter(None, deletions))
                context = list(filter(None, context))

                h = Hunk(insertions, deletions, context)

                if filename not in self.patches:
                    self.patches[filename] = {}
                if hunk_heading not in self.patches[filename]:
                    self.patches[filename][hunk_heading] = Hunk()

                # hunks may occur twice or more often
                self.patches[filename][hunk_heading].merge(h)

        self.affected = set(self.patches.keys())

    @staticmethod
    def get_filename(a, b):
        """
        get_filename: Determine the filename of a diff of a file
        """
        # chomp preceeding a/'s and b/'s
        if a.startswith('a/'):
            a = a[2:]
        if b.startswith('b/'):
            b = b[2:]

        if a == b:
            return a
        elif a == '/dev/null' and b != '/dev/null':
            return b
        elif b == '/dev/null' and a != '/dev/null':
            return a

        # If everything else fails, try to drop everything before the first '/'
        a = a.split('/', 1)[1]
        b = b.split('/', 1)[1]
        if a == b:
            return a

        # If it still fails, return the longest common suffix
        a_sfx = a[-len(b):]
        b_sfx = b[-len(a):]
        while a_sfx != b_sfx:
            a_sfx = a_sfx[1:]
            b_sfx = b_sfx[1:]

        # This makes only sense, if we have a few characters left
        if len(a_sfx) > 3:
            return a_sfx

        # Still not working? Ok, take the longest common prefix
        min_len = min(len(a), len(b))
        a_pfx = a[0:min_len]
        b_pfx = b[0:min_len]
        while a_pfx != b_pfx:
            a_pfx = a_pfx[0:-1]
            b_pfx = b_pfx[0:-1]

        # This makes only sense, if we have a few characters left
        if len(a_pfx) > 3:
            return a_pfx

        # Fail, if we're still not able to parse
        raise ValueError('Unable to parse tuple %s <-> %s' % (a, b))

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
    def __init__(self, insertions=None, deletions=None, invariant=None):
        self._insertions = insertions or []
        self._deletions = deletions or []
        self._invariant = invariant or []

    def merge(self, other):
        self._insertions += other._insertions
        self._deletions += other._deletions
        self._invariant += other._invariant
        pass

    @property
    def deletions(self):
        return self._deletions

    @property
    def insertions(self):
        return self._insertions

    @property
    def invariant(self):
        return self._invariant


class Diff:
    DIFF_SELECTOR_REGEX = re.compile(r'^[-\+@]')

    # The two-line unified diff headers
    FILE_SEPARATOR_MINUS_REGEX = re.compile(r'^--- ([^\s]*).*$')
    FILE_SEPARATOR_PLUS_REGEX = re.compile(r'^\+\+\+ ([^\s]*).*$')

    # Exclude '--cc' diffs
    EXCLUDE_CC_REGEX = re.compile(r'^diff --cc (.+)$')

    # Hunks inside a file
    HUNK_REGEX = re.compile(r'^@@ -([0-9]+),?([0-9]+)? \+([0-9]+),?([0-9]+)? @@ ?(.*)$')
    DIFF_REGEX = re.compile(r'^[\+-](.*)$')

    def __init__(self, patches, lines):
        self._patches = patches
        self._lines = lines

        self._affected = set()
        for i, j in self.patches.keys():
            # The [2:] will strip a/ and b/
            if '/dev/null' not in i:
                self._affected.add(i[2:])
            if '/dev/null' not in j:
                self._affected.add(j[2:])

    @property
    def lines(self):
        return self._lines

    @property
    def patches(self):
        return self._patches

    @property
    def affected(self):
        return self._affected

    @staticmethod
    def parse_diff(diff):
        # Only split at \n and not at \r
        diff = diff.split('\n')
        return Diff.parse_diff_nosplit(diff)

    @staticmethod
    def parse_diff_nosplit(diff):
        # Calculate diff_lines
        lines_of_interest = list(filter(lambda x: Diff.DIFF_SELECTOR_REGEX.match(x), diff))
        diff_lines = sum(map(len, lines_of_interest))

        # Check if we understand the diff format
        if diff and Diff.EXCLUDE_CC_REGEX.match(diff[0]):
            return Diff({}, 0)

        retval = {}

        while len(diff):
            # Consume till the first occurence of '--- '
            while len(diff):
                minus = diff.pop(0)
                if Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus):
                    break
            if len(diff) == 0:
                break
            minus = Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus).group(1)
            plus = Diff.FILE_SEPARATOR_PLUS_REGEX.match(diff.pop(0)).group(1)

            diff_index = minus, plus

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

                hunktitle = hunk.group(5)

                del_cntr = 0
                add_cntr = 0

                insertions = []
                deletions = []
                invariant = []

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

                    if identifier == '+':
                        insertions.append(payload)
                        add_cntr += 1
                    elif identifier == '-':
                        deletions.append(payload)
                        del_cntr += 1
                    elif identifier == ' ':  # invariant
                        invariant.append(payload)
                        add_cntr += 1
                        del_cntr += 1
                    elif identifier != '\\':  # '\\ No new line... statements
                        add_cntr += 1
                        del_cntr += 1

                # remove empty lines
                insertions = list(filter(None, insertions))
                deletions = list(filter(None, deletions))
                invariant = list(filter(None, invariant))

                h = Hunk(insertions, deletions, invariant)

                if diff_index not in retval:
                    retval[diff_index] = {}
                if hunktitle not in retval[diff_index]:
                    retval[diff_index][hunktitle] = Hunk()

                retval[diff_index][hunktitle].merge(h)

        return Diff(retval, diff_lines)

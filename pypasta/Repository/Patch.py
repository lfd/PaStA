"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import re
import subprocess

class Hunk:
    def __init__(self, insertions=None, deletions=None, context=None):
        self.insertions = insertions or []
        self.deletions = deletions or []
        self.context = context or []

    def merge(self, other):
        self.insertions += other.insertions
        self.deletions += other.deletions
        self.context += other.context

class Patch:
    def __init__(self, similarity=0, hunks=None):
        self.similarity = similarity
        if hunks:
            self.hunks = hunks
        else:
            self.hunks = {}


class Diff:
    # The two-line unified diff headers
    FILE_SEPARATOR_MINUS_REGEX = re.compile(r'^--- ([^\s]+).*$')
    #r'^--- (?P<filename>[^\t\n]+)(?:\t(?P<timestamp>[^\n]+))?')
    FILE_SEPARATOR_PLUS_REGEX = re.compile(r'^\+\+\+ ([^\s]+).*$')

    CONTEXT_DIFF_REGEX = re.compile(r'\*\*\*\s*\d+,\s*\d+\s*\*\*\*')

    # Exclude '--cc' diffs
    EXCLUDE_CC_REGEX = re.compile(r'^diff --cc (.+)$')

    # Hunks inside a file
    HUNK_REGEX = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?\ @@[ ]?(.*)')

    SIMILARITY_INDEX_REGEX = re.compile(r'^similarity index (\d+)\%$')
    RENAME_REGEX = re.compile(r'^(rename|copy) (from|to) (.*)$')

    LINE_IDENTIFIER_INSERTION = '+'
    LINE_IDENTIFIER_DELETION = '-'
    LINE_IDENTIFIER_CONTEXT = ' '
    LINE_IDENTIFIER_NEWLINE = '\\'

    REGEX_ORIG = re.compile(r'\.orig$')

    def __init__(self, diff):
        def insert_file(filenames, similarity):
            self.affected |= set(filenames)
            if filenames not in self.patches:
                self.patches[filenames] = Patch(similarity=similarity)

        # Check if we have a context diff. We should see something
        # like "**** 123, 456 ***" within the first few lines.
        for line in diff[0:10]:
            if Diff.CONTEXT_DIFF_REGEX.match(line):
                ctx_diff = '\n'.join(diff).encode()
                p = subprocess.run(['filterdiff', '--format=unified'],
                                   input=ctx_diff, stdout=subprocess.PIPE)
                if p.returncode != 0:
                    raise ValueError("Unable to convert context diff to unified diff")
                diff = p.stdout.decode().split('\n')
                break

        # we pop from the list until it is empty. Copy it first, to prevent its
        # deletion
        diff = diff.copy()

        self.raw = diff.copy()

        # patches store patches of files
        #  key: (filename,) or (old_filename, new_filename)
        #  value: Patch()
        self.patches = {}

        # Set of all filenames that were affected by this diff
        self.affected = set()

        self.lines = 0

        # Check if we understand the diff format
        if diff and Diff.EXCLUDE_CC_REGEX.match(diff[0]):
            return

        # We need at least three lines for any kind of reasonable patch
        while len(diff):
            self.footer = len(diff)

            # We are either looking for a line beginning with '---' or
            # a similarity index
            similarity = 0
            while len(diff):
                line = diff.pop(0)

                match = Diff.FILE_SEPARATOR_MINUS_REGEX.match(line)
                if match:
                    minus = match.group(1)
                    plus = Diff.FILE_SEPARATOR_PLUS_REGEX.match(diff.pop(0)).group(1)
                    filenames = Diff.get_filename(minus, plus)
                    break

                match = Diff.SIMILARITY_INDEX_REGEX.match(line)
                if match:
                    if len(diff) < 2:
                        print('ERROR')

                    similarity = int(match.group(1))

                    # Only consume the next two lines if the similarity is 100.
                    # If the similarity is not 100, then hunks _must_ follow.
                    if similarity == 100:
                        minus = Diff.RENAME_REGEX.match(diff.pop(0)).group(3)
                        plus= Diff.RENAME_REGEX.match(diff.pop(0)).group(3)

                        # In case we parse the 'rename from/to' lines, we must
                        # not sanitise the filenames and strip away anything
                        filenames = minus, plus

                        break

            if similarity == 100:
                insert_file(filenames, 100)
                continue

            if len(diff) == 0:
                break

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
                    elif line[0] == '\t': # we have to deal with shitty MUAs
                        identifier = ' '
                        payload = line
                    elif line[0].isspace(): # we might have UTF-8 spaces...
                        identifier = ' '
                        payload = line[1:]
                    else:
                        identifier = line[0]
                        payload = line[1:]

                    if identifier == Diff.LINE_IDENTIFIER_INSERTION:
                        insertions.append(payload)
                        add_cntr += 1
                        self.lines += 1
                    elif identifier == Diff.LINE_IDENTIFIER_DELETION:
                        deletions.append(payload)
                        del_cntr += 1
                        self.lines += 1
                    elif identifier == Diff.LINE_IDENTIFIER_CONTEXT:
                        context.append(payload)
                        add_cntr += 1
                        del_cntr += 1
                    elif identifier == Diff.LINE_IDENTIFIER_NEWLINE:  # '\ No new line' statements
                        continue
                    else:
                        # We simply ignore these lines.
                        continue

                # remove empty lines
                insertions = list(filter(None, insertions))
                deletions = list(filter(None, deletions))
                context = list(filter(None, context))

                h = Hunk(insertions, deletions, context)

                insert_file(filenames, similarity)

                if hunk_heading not in self.patches[filenames].hunks:
                    self.patches[filenames].hunks[hunk_heading] = Hunk()

                # hunks may occur twice or more often
                self.patches[filenames].hunks[hunk_heading].merge(h)
                self.footer = len(diff)

        self.affected.discard('/dev/null')

    def split_footer(self):
        if self.footer > 0:
            diff = self.raw[:-self.footer]
            footer = self.raw[-self.footer:]

            return diff, footer

        return self.raw.copy(), []

    @staticmethod
    def get_filename(a, b):
        """
        get_filename: Determine the filename of a diff of a file
        """
        def sanitise_filename(filename):
            filename = Diff.REGEX_ORIG.sub('', filename)
            if filename == '/dev/null':
                return filename

            if '/' in filename:
                filename = filename.split('/', 1)[1]

            return filename

        # chomp preceeding a/'s and b/'s
        a = sanitise_filename(a)
        b = sanitise_filename(b)

        # no move - we modify the file in place
        if a == b:
            return a,

        return a, b

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re

from enum import Enum
#import unidiff as ud
import unidiff.patch as ud

prefix_regex = re.compile('.*pre[-\s]*fix.*', re.I)

keywords = ['consti',
            #'indent',  # To be enabled
            'add', 'relicense', 'remove',
            'move', 'behavi', 'functional',
            'cleanup', 'cleaner', 'coding style', 'style', 'no need',
            'regression',
            'statici',  # staticise staticize
            'simpl',  # simpler, simplify, simple
            'readable', 'factor',
            'typo', 'performance', 'efficien', 'move',
            'preparation', 'extend', 'decrease', 'increase', 'rename',
            'aesthetic',
            'optimi',  # optimise, optimize, optimisation
            'duplicate', 'convert', 'alignment',
            'unused', 'replace', 'preparation', 'comment', 'support',
            'enable', 'failure', 'provide', 'reduction', 'implement',
            'duplicate', 'refactor', 'consistent', 'typo', 'reduce',
            'avoid', 'enable', 'new', 'correct', 'prevent', 'introduc',
            'rename', 'obsolete', 'feature', 'reliable', 'change', 'missing']


class LineType(Enum):
    Context = 0
    Inserted = 1
    Removed = 2
    Empty = 3

    @staticmethod
    def from_line(line):
        if line.is_added:
            return LineType.Inserted
        elif line.is_removed:
            return LineType.Removed
        elif line.is_context:
            return LineType.Context
        elif line.line_type == ud.LINE_TYPE_EMPTY:
            return LineType.Empty
        else:
            raise ValueError('Unknown line type')


"""
class HunkStats:
    def __init__(self):
        self._stats = {LineType.Inserted: 0,
                       LineType.Removed:  0,
                       LineType.Context:  0}
        self._modifications = 0

    @staticmethod
    def from_hunk(hunk):
        stats = HunkStats()

        previous = LineType.Context

        remove_count = 0
        insert_count = 0
        tolerance = 0

        for line in hunk:
            lineType = LineType.from_line(line)
            stats._stats[lineType] += 1

            if lineType == LineType.Removed and previous == LineType.Context:
                # Modification start indicator
                remove_count = 1
                insert_count = 0
                tolerance = 0
            elif lineType == LineType.Removed and previous == LineType.Inserted:
                raise ValueError('should not happen')
            elif lineType == LineType.Removed and previous == LineType.Removed:
                # Go on removing lines
                remove_count += 1
            elif lineType == LineType.Inserted and previous == LineType.Removed:
                # We switch from removals to insertions
                tolerance = 1
                insert_count = 1
            elif lineType == LineType.Inserted and previous == LineType.Inserted:
                insert_count += 1
            elif lineType == LineType.Context and previous == LineType.Inserted:
                # We end a modification block here
                if abs(remove_count - insert_count) <= tolerance:
                    stats._modifications += 1
                remove_count = 0
                insert_count = 0
                tolerance = 0

            previous = lineType

        return stats

    def __add__(self, other):
        result = HunkStats()
        for lineType in LineType:
            result._stats[lineType] = self._stats[lineType] + other._stats[lineType]
        result._stats[lineType] = self._modifications + other.modifications
        return result

    def __iadd__(self, other):
        for lineType in {LineType.Inserted,
                         LineType.Removed,
                         LineType.Context}:
            self._stats[lineType] += other._stats[lineType]
        self._modifications += other.modifications
        return self

    @property
    def inserted(self):
        return self._stats[LineType.Inserted]

    @property
    def removed(self):
        return self._stats[LineType.Removed]

    @property
    def context(self):
        return self._stats[LineType.Context]

    @property
    def modifications(self):
        return self._modifications
"""


def contains_fix(msg):
    # Detector for 'fix' string, but not 'prefix'
    retval = False

    for line in msg:
        if prefix_regex.match(line):
            return False
        if 'fix' in line.lower():
            retval = True

    return retval


def contains(msg, word):
    return any([word in x.lower() for x in msg])


class MyHunk:

    class BlockType(Enum):
        Context = 0
        Removal = 1
        Insertion = 2
        Change = 3

    class LineStats(dict):
        def __init__(self):
            self[LineType.Inserted] = 0
            self[LineType.Removed] = 0
            self[LineType.Context] = 0

        def __add__(self, other):
            result = MyHunk.Stats()
            for lineType in {LineType.Inserted,
                             LineType.Removed,
                             LineType.Context}:
                result[lineType] = self[lineType] + other[lineType]
            return result

        def __iadd__(self, other):
            for lineType in {LineType.Inserted,
                             LineType.Removed,
                             LineType.Context}:
                self[lineType] += other[lineType]
            return self

        @property
        def inserted(self):
            return self[LineType.Inserted]

        @property
        def removed(self):
            return self[LineType.Removed]

        @property
        def context(self):
            return self[LineType.Context]

    class BlockStats(dict):
        def __init__(self):
            self[MyHunk.BlockType.Context] = 0
            self[MyHunk.BlockType.Removal] = 0
            self[MyHunk.BlockType.Insertion] = 0
            self[MyHunk.BlockType.Change] = 0

        def __add__(self, other):
            result = MyHunk.Stats()
            for blockType in MyHunk.BlockType:
                result[blockType] = self[blockType] + other[blockType]
            return result

        def __iadd__(self, other):
            for blockType in MyHunk.BlockType:
                self[blockType] += other[blockType]
            return self

        @property
        def context(self):
            return self[MyHunk.BlockType.Context]

        @property
        def removal(self):
            return self[MyHunk.BlockType.Removal]

        @property
        def insertion(self):
            return self[MyHunk.BlockType.Insertion]

        @property
        def change(self):
            return self[MyHunk.BlockType.Change]


    def __init__(self, hunk):
        self._blocks = []
        self._line_stats = MyHunk.LineStats()
        self._block_stats = MyHunk.BlockStats()

        def append(type, block):
            self._blocks.append((type, block))
            self._block_stats[type] += 1

        previous = LineType.Empty
        current_block = []

        remove_count = 0
        insert_count = 0

        last_line = ud.Line('', ud.LINE_TYPE_EMPTY)

        for line in hunk + [last_line]:
            lineType = LineType.from_line(line)

            # We hit the last line
            if lineType == LineType.Empty:
                # Fake last line
                if previous == LineType.Context:
                    lineType = LineType.Inserted
                else:
                    lineType = LineType.Context
            else:
                self._line_stats[lineType] += 1

            # We hit the first line
            if previous == LineType.Empty:
                if lineType == LineType.Inserted:
                    insert_count = 1
                    current_block = [line]
                elif lineType == LineType.Removed:
                    remove_count = 1
                    current_block = [line]
                elif lineType == LineType.Context:
                    current_block = [line]
                else:
                    raise NotImplemented('Should not happen')
            elif previous == LineType.Context:
                if lineType == LineType.Context:
                    current_block.append(line)
                elif lineType == LineType.Inserted:
                    append(MyHunk.BlockType.Context, current_block)
                    current_block = [line]
                    insert_count = 1
                elif lineType == LineType.Removed:
                    append(MyHunk.BlockType.Context, current_block)
                    current_block = [line]
                    remove_count = 1
                else:
                    raise NotImplementedError('Unknown line type')
            elif previous == LineType.Inserted:
                if lineType == LineType.Context:
                    append(MyHunk.BlockType.Change, current_block)
                    current_block = [line]
                    remove_count = 0
                    insert_count = 0
                elif lineType == LineType.Inserted:
                    insert_count += 1
                    current_block.append(line)
                elif lineType == LineType.Removed:
                    raise NotImplementedError('Should not happen')
                else:
                    raise NotImplementedError('Unknown line type')
            elif previous == LineType.Removed:
                if lineType == LineType.Context:
                    append(MyHunk.BlockType.Removal, current_block)
                    current_block = [line]
                    remove_count = 0
                    insert_count = 0
                elif lineType == LineType.Inserted:
                    current_block.append(line)
                    insert_count = 1
                elif lineType == LineType.Removed:
                    remove_count += 1
                    current_block.append(line)
                else:
                    raise NotImplementedError('Unknown line type')
            else:
                raise NotImplementedError('Unknown line type')

            previous = lineType

    @property
    def line_stats(self):
        return self._line_stats

    @property
    def block_stats(self):
        return self._block_stats


def num_indents(hunk):

    ni = 0
    return ni


def get_features(repo, hash):
    commit = repo[hash]
    msg = commit.message

    patchSet = ud.PatchSet(commit.diff.raw)
    features = []

    for k in keywords:
        features.append(contains(msg, k))

    hunks = 0
    num_ind = 0
    overall_line_stat = MyHunk.LineStats()
    overall_block_stat = MyHunk.BlockStats()
    for patch in patchSet:
        for hunk in patch:
            hunks += 1
            myHunk = MyHunk(hunk)
            overall_line_stat += myHunk.line_stats
            overall_block_stat += myHunk.block_stats

    features.append(hunks)

    features.append(overall_line_stat.inserted)
    features.append(overall_line_stat.removed)
    features.append(overall_line_stat.context)

    features.append(overall_block_stat.insertion)
    features.append(overall_block_stat.removal)
    features.append(overall_block_stat.context)
    features.append(overall_block_stat.change)

    return features

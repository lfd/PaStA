"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re

from .Patch import Diff


class Signature:
    def __init__(self, name, email, date):
        self.name = name
        self.email = email
        self.date = date


class MessageDiff:
    """
    An abstract class that consists of a message, and a diff.
    """
    SIGN_OFF_REGEX = re.compile(r'^('
                                r'Signed-off-by:|'
                                r'Acked-by:|'
                                r'Link:|'
                                r'CC:|'
                                r'Reviewed-by:|'
                                r'Reported-by:|'
                                r'Tested-by:|'
                                r'LKML-Reference:|'
                                r'Patch:|'
                                r'Wrecked-off-by:|'
                                r'Gitweb:|'
                                r'Merge:|'
                                r'Fixes:|'
                                r'Commit:|'
                                r'Patchwork:|'
                                r'From:|'
                                r'Commit-ID:|'
                                r'Author:|'
                                r'AuthorDate:|'
                                r'Committer:|'
                                r'CommitDate:'
                                r')',
                                re.IGNORECASE)

    def __init__(self, identifier, content, author):
        self.identifier = identifier
        self.author = author

        message, self.annotation, diff = content
        self.raw_message = message

        self._is_merge_commit = False

        # Split by linebreaks and filter empty lines
        message = list(filter(None, message))
        # Filter signed-off-by lines
        filtered = list(filter(lambda x: not MessageDiff.SIGN_OFF_REGEX.match(x),
                               message))

        if len(filtered) > 1 and filtered[0] == filtered[1]:
            filtered.pop(0)

        # if the filtered result is empty, then leave at least one line
        if filtered:
            message = filtered

        self.message = message

        # is a revert message?
        self.is_revert = any('revert' in x.lower() for x in self.raw_message)

        # do the tricky part: parse the diff
        self.diff = Diff(diff)

    def format_message(self, custom):
        type = 'Commit:    ' if self.identifier[0] != '<' else 'Message-ID:'

        message = ['%s %s' % (type, self.identifier),
                   'Author:     %s <%s>' %
                   (self.author.name, self.author.email),
                   'AuthorDate: %s' % self.author.date]
        message += custom + [''] + self.raw_message

        return message

    @property
    def is_merge_commit(self):
        return self._is_merge_commit

    @property
    def subject(self):
        return self.message[0]

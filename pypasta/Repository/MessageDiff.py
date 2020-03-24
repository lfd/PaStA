"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2019

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re
from collections import defaultdict

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

    # Tags used in Linux kernel mailing lists
    VALID_TAGS = (r'^('
                  'Signed-off-by|'
                  'Acked-by|'
                  'Link|'
                  'CC|'
                  'Reviewed-by|'
                  'Reported-by|'
                  'Tested-by|'
                  'LKML-Reference|'
                  'Patch|'
                  'Wrecked-off-by|'
                  'Gitweb|'
                  'Merge|'
                  'Fixes|'
                  'Commit|'
                  'Patchwork|'
                  'From|'
                  'Commit-ID|'
                  'Author|'
                  'AuthorDate|'
                  'Committer|'
                  'CommitDate'
                  ')')
    TAG_REGEX = re.compile(r'^%s\s*:\s*(.*)$' % VALID_TAGS, re.IGNORECASE)
    LINUX_ML_PREFIX = re.compile(r'https?://(lore|lkml).kernel.org')

    def __init__(self, identifier, content, author):
        self.identifier = identifier
        self.author = author

        message, self.annotation, diff = content
        self.raw_message = message

        # Split by linebreaks and filter empty lines
        message = list(filter(None, message))

        self.tags = defaultdict(list)
        self.message = []

        for line in message:
            line = line.strip()
            match = MessageDiff.TAG_REGEX.match(line)
            if not match:
                self.message.append(line)
            else:
                tag, content = match.group(1), match.group(2)
                self.tags[tag.lower().strip()].append(content.strip())

        # Handle cases where the subject line is duplicated
        if len(self.message) > 1 and self.message[0] == self.message[1]:
            self.message.pop(0)

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
    def subject(self):
        return self.message[0]

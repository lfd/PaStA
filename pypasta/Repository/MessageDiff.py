"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016-2017

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re

from .Patch import Diff


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

    def __init__(self, message, diff, author_name, author_email, author_date,
                 snip_header=False):
        self.author = author_name
        self.author_email = author_email
        self.author_date = author_date
        self.raw_message = message

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

        def snips(line):
            return '-------' in line or '--8<--' in line

        self.header = []
        if snip_header:
            if any(snips(line) for line in message[0:4]):
                line = message.pop(0)
                while not snips(line):
                    self.header.append(line)
                    line = message.pop(0)
                self.header.append(line)
        self.message = message

        # is a revert message?
        self.is_revert = any('revert' in x.lower() for x in self.raw_message)

        # do the tricky part: parse the diff
        self.diff = Diff(diff)

    def format_message(self, custom):
        message = ['Commit:     %s' % self.commit_hash,
                   'Author:     %s <%s>' %
                   (self.author, self.author_email),
                   'AuthorDate: %s' % self.author_date]
        message += custom + [''] + self.raw_message

        return message

    @property
    def subject(self):
        return self.message[0]

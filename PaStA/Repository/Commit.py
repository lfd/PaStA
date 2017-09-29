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

    SIGN_OFF_REGEX = re.compile((r'^(Signed-off-by:|Acked-by:|Link:|CC:|Reviewed-by:'
                                 r'|Reported-by:|Tested-by:|LKML-Reference:|Patch:)'
                                 r'|Wrecked-off-by:'),
                                re.IGNORECASE)

    REVERT_REGEX = re.compile(r'revert', re.IGNORECASE)

    def __init__(self, message, diff, author_name, author_email, author_date):

        self.author = author_name
        self.author_email = author_email
        self.author_date = author_date

        if isinstance(message, list):
            self.raw_message = '\n'.join(message)
            self.message = message
        else:
            self.raw_message = message
            self.message = message.split('\n')

        # Split by linebreaks and filter empty lines
        self.message = list(filter(None, self.message))
        # Filter signed-off-by lines
        filtered = list(filter(lambda x: not Commit.SIGN_OFF_REGEX.match(x), self.message))

        # if the filtered result is empty, then leave at least one line
        if not filtered:
            self.message = [self.message[0]]
        else:
            self.message = filtered

        # Is a revert message?
        self.is_revert = bool(Commit.REVERT_REGEX.search(self.raw_message))

        if isinstance(diff, list):
            self.raw_diff = '\n'.join(diff)
            self.diff = Diff.parse_diff_nosplit(diff)
        else:
            self.raw_diff = diff
            self.diff = Diff.parse_diff(diff)

    @property
    def subject(self):
        return self.message[0]


class PatchMail(MessageDiff):
    def __init__(self, message_id, message, diff,
                 author_name, author_email, author_date,
                 mail_subject):
        super(PatchMail, self).__init__(message, diff, author_name,
                                        author_email, author_date)

        # Simply name it commit_hash, otherwise we would have to refactor
        # tons of code.
        self.commit_hash = message_id

        self.mail_subject = mail_subject


class Commit(MessageDiff):
    def __init__(self, commit_hash, message, diff,
                 author_name, author_email, author_date,
                 committer, committer_email, commit_date,
                 note=None):
        super(Commit, self).__init__(message, diff, author_name, author_email,
                                     author_date)

        self.commit_hash = commit_hash

        self.committer = committer
        self.committer_email = committer_email
        self.commit_date = commit_date

        self.note = note

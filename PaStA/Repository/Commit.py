"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2016

Author:
  Ralf Ramsauer <ralf.ramsauer@othr.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""
import re

from .Patch import Diff


class Commit:
    SIGN_OFF_REGEX = re.compile((r'^(Signed-off-by:|Acked-by:|Link:|CC:|Reviewed-by:'
                                 r'|Reported-by:|Tested-by:|LKML-Reference:|Patch:)'),
                                re.IGNORECASE)
    REVERT_REGEX = re.compile(r'revert', re.IGNORECASE)

    def __init__(self, commit_hash, message, diff,
                 author, author_email, author_date,
                 committer, committer_email, commit_date,
                 note=None):

        self._commit_hash = commit_hash

        if isinstance(message, list):
            self._raw_message = '\n'.join(message)
            self._message = message
        else:
            self._raw_message = message
            self._message = message.split('\n')

        # Split by linebreaks and filter empty lines
        self._message = list(filter(None, self._message))
        # Filter signed-off-by lines
        filtered = list(filter(lambda x: not Commit.SIGN_OFF_REGEX.match(x), self._message))

        # if the filtered result is empty, then leave at least one line
        if not filtered:
            self._message = [self._message[0]]
        else:
            self._message = filtered

        self._committer = committer
        self._committer_email = committer_email
        self._commit_date = commit_date

        self._author = author
        self._author_email = author_email
        self._author_date = author_date

        # Is a revert message?
        self._is_revert = bool(Commit.REVERT_REGEX.search(self._raw_message))

        if isinstance(diff, list):
            self._raw_diff = '\n'.join(diff)
            self._diff = Diff.parse_diff_nosplit(diff)
        else:
            self._raw_diff = diff
            self._diff = Diff.parse_diff(diff)

        self._note = note

    @property
    def commit_hash(self):
        return self._commit_hash

    @property
    def is_revert(self):
        return self._is_revert

    @property
    def raw_diff(self):
        return self._raw_diff

    @property
    def diff(self):
        return self._diff

    @property
    def raw_message(self):
        return self._raw_message

    @property
    def message(self):
        return self._message

    @property
    def subject(self):
        return self._message[0]

    @property
    def author(self):
        return self._author

    @property
    def author_email(self):
        return self._author_email

    @property
    def author_date(self):
        return self._author_date

    @property
    def committer(self):
        return self._committer

    @property
    def committer_email(self):
        return self._committer_email

    @property
    def commit_date(self):
        return self._commit_date

    @property
    def note(self):
        return self._note

"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2021

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import csv
import email
import re
from anytree import LevelOrderIter
from enum import Enum

from .MAINTAINERS import load_maintainers
from .Util import get_first_upstream, mail_parse_date


VALID_EMAIL_REGEX = re.compile(r'.+@.+\..+')


class PatchType(Enum):
    PATCH = 'patch' # A regular patch written by a human author
    BOT = 'bot'
    NEXT = 'linux-next'
    STABLE = 'stable-review'
    NOT_PROJECT = 'not-project'
    PROCESS = 'process'
    NOT_FIRST = 'not-first' # Mail contains a patch, but it's not the first patch in the thread
    OTHER = 'other'


def email_get_recipients(message):
    recipients = message.get_all('To', []) + message.get_all('Cc', [])
    recipients = list(filter(None, recipients))
    # get_all might return Header objects. Convert them all to strings.
    recipients = [str(x) for x in recipients]

    # Only accept valid email addresses
    recipients = {x[1].lower() for x in email.utils.getaddresses(recipients)
                  if VALID_EMAIL_REGEX.match(x[1])}

    return recipients


def email_get_header_normalised(message, header):
    header = str(message[header] or '').lower()
    header = header.replace('\n', '').replace('\t', ' ')

    return header


def email_get_from(message):
    mail_from = email_get_header_normalised(message, 'From')
    return email.utils.parseaddr(mail_from)


class MailCharacteristics:
    REGEX_COVER = re.compile('\[.*patch.*\s0+/.*\].*', re.IGNORECASE)

    @staticmethod
    def dump_release_info(config):
        relevant_releases = [
            (tag, date.strftime('%Y-%m-%d')) for tag, date in config.repo.tags if
                config.mbox_mindate < date.replace(tzinfo=None) < config.mbox_maxdate and
                '-rc' not in tag
        ]
        with open(config.f_releases, 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=['release', 'date'])
            writer.writeheader()
            for release, date in relevant_releases:
                writer.writerow({'release': release,
                                 'date': date})

    def _has_foreign_response(self, repo):
        """
        This function will return True, if there's another author in this
        thread, other than the ORIGINAL author. (NOT the author of this
        email)
        """
        if len(self.thread.children) == 0:
            return False  # If there is no response the check is trivial

        for mail in list(LevelOrderIter(self.thread)):
            # Beware, the mail might be virtual
            if mail.name not in repo:
                continue

            this_email = email_get_from(repo.mbox.get_messages(mail.name)[0])[1]
            if this_email != self.mail_from[1]:
                return True
        return False

    def _patches_project(self):
        for affected in self.patch.diff.affected:
            if True in map(lambda x: affected.startswith(x),
                           self.ROOT_DIRS) or \
               affected in self.ROOT_FILES:
                continue
            return False
        return True

    def _analyse_series(self):
        if self.is_patch:
            if self.message_id == self.thread.name or \
               self.message_id in [x.name for x in self.thread.children]:
                self.is_first_patch_in_thread = True
        elif 'Subject' in self.message and \
             MailCharacteristics.REGEX_COVER.match(str(self.message['Subject'])):
            self.is_cover_letter = True

    def _cleanup(self):
        del self.message
        del self.patch

    def __init__(self, repo, clustering, message_id):
        self.message_id = message_id

        self.message = repo.mbox.get_messages(message_id)[0]
        self.thread = repo.mbox.threads.get_thread(message_id)
        self.recipients = email_get_recipients(self.message)

        self.recipients_lists = self.recipients & repo.mbox.lists
        self.recipients_other = self.recipients - repo.mbox.lists

        self.mail_from = email_get_from(self.message)
        self.subject = email_get_header_normalised(self.message, 'Subject')
        self.date = mail_parse_date(self.message['Date'])

        self.lists = repo.mbox.get_lists(message_id)

        # Patch characteristics
        self.is_patch = message_id in repo and message_id not in repo.mbox.invalid
        self.patch = None

        self.patches_project = False
        self.has_foreign_response = None
        self.first_upstream = None
        self.committer = None
        self.integrated_correct = None
        self.integrated_xcorrect = None

        self.version = None

        self.is_cover_letter = False
        self.is_first_patch_in_thread = False
        self.process_mail = False

        self.is_from_bot = None
        self._analyse_series()

        # By default, assume type 'other'
        self.type = PatchType.OTHER

        if not self.is_patch:
            return

        self.patch = repo[message_id]

        # We must only analyse foreign responses of patches if the patch is
        # the first patch in a thread. Otherwise, we might not be able to
        # determine the original author of a thread. Reason: That mail
        # might be missing.
        if self.is_first_patch_in_thread:
            self.has_foreign_response = self._has_foreign_response(repo)
        elif self.type == PatchType.OTHER:
            self.type = PatchType.NOT_FIRST

        self.process_mail = True in [process in self.subject for process in self.PROCESSES]
        if self.process_mail:
            self.type = PatchType.PROCESS

        self.patches_project = self._patches_project()
        if not self.patches_project:
            self.type = PatchType.NOT_PROJECT
        # Even if the patch does not patch Linux, we can assign it to a
        # appropriate version
        self.version = repo.patch_get_version(self.patch)

        self.first_upstream = get_first_upstream(repo, clustering, message_id)


def load_characteristics(config, clustering):
    """
    This routine loads characteristics for ALL mails in the time window
    config.mbox_timewindow, and loads multiple instances of maintainers for the
    patches of the clustering.
    """
    from .LinuxMailCharacteristics import load_linux_mail_characteristics
    _load_characteristics = {
        'linux': load_linux_mail_characteristics,
    }

    repo = config.repo

    # Characteristics need thread information. Ensure it's loaded.
    repo.mbox.load_threads()

    all_messages_in_time_window = repo.mbox.get_ids(config.mbox_time_window,
                                                    allow_invalid=True)

    if config.project_name in _load_characteristics:
        return _load_characteristics[config.project_name](config, clustering, all_messages_in_time_window)
    else:
        raise NotImplementedError('Missing code for project %s' % config.project_name)

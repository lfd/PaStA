"""
PaStA - Patch Stack Analysis

Copyright (c) OTH Regensburg, 2018

Author:
  Ralf Ramsauer <ralf.ramsauer@oth-regensburg.de>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

import os
import pickle
import re

from collections import defaultdict
from email.header import Header
from anytree import Node, RenderTree
from itertools import chain
from logging import getLogger
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

log = getLogger(__name__[-15:])

ID_REGEX = re.compile(r'(<\S+>)')
_mbox = None


def sanitise_header(message, header):
    contents = message.get_all(header)
    ids = set()

    if not contents:
        return ids

    for content in contents:
        # special treatment for mails with unknown encoding in their headers
        if isinstance(content, Header):
            content = bytearray(content._chunks[0][0], 'utf-8',
                                'ignore').decode()

        ids |= set(ID_REGEX.findall(content))

    return ids


def get_irts(id):
    messages = _mbox.get_messages(id)
    irt = set()
    ids = set()

    for message in messages:
        irt |= sanitise_header(message, 'in-reply-to')
        ids |= sanitise_header(message, 'message-id')

    irt -= ids

    return id, irt


class MailThread:
    def __init__(self, mbox, f_cache):
        self.f_cache = f_cache
        self.reply_to_dict = defaultdict(set)
        self.parents = set()
        self.mbox = mbox

    def update(self, parallelise=True):
        log.info('Updating mail thread cache')
        all_messages = self.mbox.get_ids(allow_invalid=True)
        present = set(chain.from_iterable(self.reply_to_dict.values()))
        victims = all_messages - present - self.parents
        length = len(victims)
        if len(victims) == 0:
            log.info('Cache is already up to date')
            return

        log.info('Creating caches for %d mails' % length)

        global _mbox
        _mbox = self.mbox

        if parallelise:
            with Pool(cpu_count()) as p:
                irt_list = list(tqdm(p.imap(get_irts, victims), total=length))
        else:
            irt_list = list(tqdm(map(get_irts, victims), total=length))

        _mbox = None

        for id, irts in tqdm(irt_list):
            # If there are no In-Reply-To headers, then the mail is the parent
            # of a thread.
            if not irts:
                self.parents.add(id)
                continue

            # Otherwise, let the father point to his children
            for irt in irts:
                self.reply_to_dict[irt].add(id)

        log.info('Writing mailbox thread cache...')
        _mbox = self.mbox
        self.mbox = None
        pickle.dump(self, open(self.f_cache, 'wb'))
        self.mbox = _mbox
        _mbox = None
        log.info('  ↪ done')

    def _get_thread(self, node, visited):
        this_id = node.name

        # visited tracks visited mails, used to eliminate cycles
        visited.add(this_id)

        if this_id not in self.reply_to_dict:
            return
        responses = self.reply_to_dict[this_id]

        for response in responses:
            if response in visited:
                continue

            child = Node(response, parent=node)
            if response not in self.reply_to_dict:
                continue
            self._get_thread(child, visited)

    def pretty_print(self, thread):
        for pre, fill, node in RenderTree(thread):
            if node.name in self.mbox:
                message = self.mbox.get_messages(node.name)[0]
                print('%.20s\t\t%s%s' % (message['From'], pre, node.name))
            else: # We may have a virtual email
                print('%.20s\t\t %s' % ('VIRTUAL EMAIL', node.name))

    def get_parent(self, message_id, visited):
        # visited tracks visited mails, used to eliminate cycles
        visited.add(message_id)
        # FIXME respect non-unique message ids
        message = self.mbox.get_messages(message_id)[0]
        if message is None:
            return message_id

        # get the parent message-id by walking up references an in-reply-to
        # header. Remove the own message it, as it must not be a reference.
        references = sanitise_header(message, 'references') | \
                     sanitise_header(message, 'in-reply-to')
        references.discard(message_id)
        if not references:
            return message_id

        virtual_parents = set()
        for reference in references:
            if reference in visited:
                continue
            if reference in self.mbox:
                return self.get_parent(reference, visited)
            else:
                virtual_parents.add(reference)

        # We may have more than one virtual parent, but deterministically
        # return the first one.
        if len(virtual_parents) > 1:
            return sorted(virtual_parents)[0]

        return message_id

    def get_thread(self, message_id):
        parent = self.get_parent(message_id, set())
        head = Node(parent)
        self._get_thread(head, set())
        return head

    @staticmethod
    def load(filename, mbox):
        if os.path.isfile(filename):
            with open(filename, 'rb') as f:
                mailthreads = pickle.load(f)
            mailthreads.mbox = mbox
            mailthreads.f_cache = filename
            return mailthreads
        log.warning('MailThread cache not existing')
        return MailThread(mbox, filename)

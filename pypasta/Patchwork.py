"""
PaStA - Patch Stack Analysis

Copyright (C) 2019, Bayerische Motoren Werke Aktiengesellschaft (BMW AG)

Author:
  Mete Polat <metepolat2000@gmail.com>

This work is licensed under the terms of the GNU GPL, version 2.  See
the COPYING file in the top-level directory.
"""

from urllib.parse import urljoin

import requests
from datetime import datetime


class Patchwork:

    def __init__(self, **kwargs):
        self.url = kwargs['url']
        self.token = kwargs.get('token')
        username = kwargs.get('username')
        password = kwargs.get('password')
        self.basic_auth = None
        if username and password:
            self.basic_auth = (username, password)

    @property
    def auth(self) -> dict:
        if not self.token and not self.basic_auth:
            raise ValueError(
                "Authentication required. No username/password or api_token "
                "provided in config")
        if self.token:
            return {'headers': {'Authorization': 'Token ' + self.token}}
        else:
            return {'auth': self.basic_auth}

    @staticmethod
    def page_iterator(resp, yield_value):
        while True:
            for item in resp.json():
                value = yield_value(item)
                if value:
                    yield value

            next_page = resp.links.get('next', None)
            if next_page is None:
                break
            resp = requests.get(next_page['url'])

    def download_patches(self, since: datetime, lists, ignore):
        def yield_value(event):
            date = datetime.fromisoformat(event['date'])
            patch = event['payload']['patch']
            list_id = event['project']['list_id']
            msg_id = patch['msgid']
            mbox_url = patch['mbox']

            if list_id not in lists or msg_id in ignore:
                # None skips yielding a value
                return None

            resp_mbox = requests.get(mbox_url)
            return date, list_id, msg_id, resp_mbox.text

        params = {'category': 'patch-created'}
        if since is not None:
            params['since'] = since.isoformat()
        resp = requests.get(urljoin(self.url, 'events'), params)
        return self.page_iterator(resp, yield_value)

    def insert_relation(self, related):
        url = urljoin(self.url, 'relations/')
        resp = requests.post(url, json={'submissions': related}, **self.auth)
        resp.raise_for_status()

    def update_commit_ref(self, patch_id, commit_ref):
        data = {'commit_ref': commit_ref}
        url = urljoin(self.url, 'patches/%d/' % patch_id)
        resp = requests.patch(url, json=data, **self.auth)
        resp.raise_for_status()

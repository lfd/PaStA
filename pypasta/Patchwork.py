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
        self.project_id = kwargs['project_id']
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
    def page_iterator(resp, yield_value, since):
        done = False
        while True:
            if resp.status_code != 200:
                break
            for item in resp.json():
                value = yield_value(item)
                if value:
                    if since is not None:
                        if value[-1] == since:
                            done = True
                            break
                    yield value
            if done:
                break
            next_page = resp.links.get('next', None)
            if next_page is None:
                break
            resp = requests.get(next_page['url'])

    # downloads all patches since the patch with patchwork id: since. If since is None will download all patches.
    # In the worst case will lead to fetching an extra page of patches.
    def download_patches(self, project_id, since=None):

        def yield_value(patch):
            patchwork_id = patch['id']
            date = datetime.fromisoformat(patch['date'])
            msg_id = patch['msgid']
            mbox_url = patch['mbox']
            resp_mbox = requests.get(mbox_url)

            return date, msg_id, resp_mbox.text, patchwork_id

        params = {}
        params['order'] = '-id'   # descending id order
        params['project'] = project_id
        resp = requests.get(urljoin(self.url, 'patches'), params)
        return self.page_iterator(resp, yield_value, since)

    def insert_relation(self, related):
        url = urljoin(self.url, 'relations/')
        resp = requests.post(url, json={'submissions': related}, **self.auth)
        resp.raise_for_status()

    def update_commit_ref(self, patch_id, commit_ref):
        data = {'commit_ref': commit_ref}
        url = urljoin(self.url, 'patches/%d/' % patch_id)
        resp = requests.patch(url, json=data, **self.auth)
        resp.raise_for_status()

    def get_patchwork_id(self, msg_id):
        url = urljoin(self.url, 'patches')
        resp = requests.get(url, params={'msgid': msg_id})
        if resp is not None:
            resp = resp.json()
            if len(resp) != 0:
                return resp[0]['id']
        return None

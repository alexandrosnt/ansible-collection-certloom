# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

"""Small client for the certloom REST API, shared by the modules.

Only ansible.module_utils is used, so nothing has to be installed on the
host that runs the modules.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import time
import uuid
from urllib.parse import quote, urlencode

from ansible.module_utils.urls import fetch_url

MAX_RETRIES = 3
MAX_WAIT = 30


def argument_spec(**module_spec):
    """Return the connection options merged with the module's own options."""
    spec = dict(
        url=dict(type='str', fallback=(env_fallback_str, ['CERTLOOM_ENDPOINT'])),
        token=dict(type='str', no_log=True, fallback=(env_fallback_str, ['CERTLOOM_TOKEN'])),
        ca_path=dict(type='path'),
        validate_certs=dict(type='bool', default=True),
        timeout=dict(type='int', default=60),
    )
    spec.update(module_spec)
    return spec


def env_fallback_str(*names):
    # Like ansible.module_utils.basic.env_fallback, but an empty variable
    # counts as unset so the "required" message below is the one users see.
    from ansible.module_utils.basic import AnsibleFallbackNotFound
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    raise AnsibleFallbackNotFound


def ref(value):
    """Escape an id or name for use as one path segment."""
    return quote(str(value), safe='')


class APIError(Exception):
    """A problem response (RFC 9457) or a transport error."""

    def __init__(self, status, title='', detail='', request_id=''):
        self.status = status
        self.title = title
        self.detail = detail
        self.request_id = request_id
        msg = detail or title or 'request failed'
        if request_id:
            msg = '%s (request %s)' % (msg, request_id)
        super(APIError, self).__init__('certloom API %s: %s' % (status, msg))


class Client:
    def __init__(self, module):
        self.module = module
        p = module.params
        if not p.get('url'):
            module.fail_json(msg='url is required (or set CERTLOOM_ENDPOINT)')
        if not p.get('token'):
            module.fail_json(msg='token is required (or set CERTLOOM_TOKEN)')
        self.base = p['url'].rstrip('/')
        if not self.base.startswith(('https://', 'http://')):
            module.fail_json(msg='url must start with https:// or http://')
        self.token = p['token']
        self.timeout = p.get('timeout') or 60
        self.ca_path = p.get('ca_path')

    def request(self, method, path, body=None, raw=None, query=None, if_match=None):
        """Send one request and return the decoded JSON body (or None).

        POST carries an Idempotency-Key, so a retried create that the server
        already finished is replayed instead of repeated. 429 and 503 are
        retried with Retry-After for any method.
        """
        target = self.base + path
        if query:
            target += '?' + urlencode(query)
        headers = {
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/json',
        }
        data = None
        if raw is not None:
            data = raw
            headers['Content-Type'] = 'application/yaml'
        elif body is not None:
            data = json.dumps(body)
            headers['Content-Type'] = 'application/json'
        if method == 'POST':
            headers['Idempotency-Key'] = uuid.uuid4().hex
        if if_match:
            headers['If-Match'] = '"v%d"' % if_match

        attempt = 0
        while True:
            resp, info = fetch_url(self.module, target, data=data, headers=headers, method=method,
                                   timeout=self.timeout, ca_path=self.ca_path)
            status = info.get('status', -1)
            if 200 <= status < 300:
                content = resp.read() if resp else b''
                return json.loads(content) if content else None
            wait = self._retry_wait(status, info, attempt)
            if wait is None:
                raise self._error(status, info)
            time.sleep(wait)
            attempt += 1

    @staticmethod
    def _retry_wait(status, info, attempt):
        if attempt >= MAX_RETRIES or status not in (429, 503):
            return None
        wait = 2 ** attempt
        value = info.get('retry-after')
        if value is not None:
            try:
                wait = int(value)
            except ValueError:
                pass
        if wait > MAX_WAIT:
            return None
        return max(wait, 0)

    @staticmethod
    def _error(status, info):
        if status < 0:
            return APIError(status, detail=info.get('msg', 'connection failed'))
        try:
            problem = json.loads(info.get('body') or b'{}')
        except ValueError:
            problem = {}
        if not isinstance(problem, dict):
            problem = {}
        return APIError(status, problem.get('title') or info.get('msg', ''),
                        problem.get('detail', ''), problem.get('request_id', ''))

    def get(self, path):
        """GET path, returning None on 404."""
        try:
            return self.request('GET', path)
        except APIError as e:
            if e.status == 404:
                return None
            raise

    def list(self, path):
        return (self.request('GET', path) or {}).get('items') or []

    def delete(self, path):
        """DELETE path; an object that is already gone is not an error."""
        try:
            self.request('DELETE', path)
        except APIError as e:
            if e.status != 404:
                raise


class Result:
    """Collects what a module did to one object, for exit_json and --diff."""

    def __init__(self, module, key, current):
        self.module = module
        self.key = key
        self.changed = False
        self.before = dict(current or {})
        self.obj = dict(current or {})

    def create(self, client, path, body, preview=None):
        """POST body to path, or in check mode report preview (default body)."""
        self.changed = True
        if self.module.check_mode:
            self.obj = dict(preview if preview is not None else body)
        else:
            self.obj = client.request('POST', path, body=body)
        return self.obj

    def update(self, client, path, body, method='PATCH', if_match=None, preview=None):
        """Send a partial update; body holds only the changed fields.

        In check mode the fields in preview (default body) are merged into
        the object; pass preview when body is not in the object's terms or
        holds a secret.
        """
        self.changed = True
        if self.module.check_mode:
            self.obj = dict(self.obj, **(preview if preview is not None else body))
        else:
            self.obj = client.request(method, path, body=body, if_match=if_match) or self.obj
        return self.obj

    def delete(self, client, path):
        self.changed = True
        self.obj = {}
        if not self.module.check_mode:
            client.delete(path)

    def exit(self, **extra):
        out = {self.key: self.obj}
        out.update(extra)
        if self.changed:
            out['diff'] = dict(before=self.before, after=self.obj)
        self.module.exit_json(changed=self.changed, **out)


def run_info(module, path, key):
    """Exit with the objects at path, or only the one named module.params['name']."""
    def fetch(client):
        items = client.list(path)
        name = module.params.get('name')
        if name:
            items = [i for i in items if name in (i.get('id'), i.get('name'))]
        module.exit_json(changed=False, **{key: items})
    run(module, fetch)


def changes(current, wanted):
    """Return the keys of wanted whose value differs from current.

    A wanted value of None means the user left the option out.
    """
    return sorted(k for k, v in wanted.items() if v is not None and current.get(k) != v)


def run(module, fn):
    """Call fn(client) and turn API errors into fail_json."""
    try:
        fn(Client(module))
    except APIError as e:
        msg = str(e)
        if e.status == 412:
            msg += '; the object changed while this task ran, run it again'
        module.fail_json(msg=msg, status=e.status)

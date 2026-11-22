# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

import pytest

from ansible_collections.certloom.certloom.plugins.module_utils import api


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body


class FakeModule:
    def __init__(self, **params):
        self.params = dict(url='https://certloom.example.test', token='t', ca_path=None,
                           validate_certs=True, timeout=5)
        self.params.update(params)
        self.check_mode = False
        self.failed = None

    def fail_json(self, **kw):
        self.failed = kw
        raise SystemExit(1)


@pytest.fixture
def calls(monkeypatch):
    """Replace fetch_url with a queue of canned (status, body, headers) answers."""
    sent = []
    answers = []

    def fake_fetch(module, url, data=None, headers=None, method=None, timeout=None, ca_path=None):
        sent.append(dict(url=url, data=data, headers=dict(headers), method=method))
        status, body, extra = answers.pop(0)
        info = dict(status=status, msg='HTTP %d' % status)
        info.update(extra)
        if 200 <= status < 300:
            return FakeResponse(body), info
        info['body'] = body
        return None, info

    monkeypatch.setattr(api, 'fetch_url', fake_fetch)
    monkeypatch.setattr(api.time, 'sleep', lambda s: sent.append(dict(slept=s)))
    return sent, answers


def test_post_sends_idempotency_key_and_reuses_it_on_retry(calls):
    sent, answers = calls
    answers.extend([(503, b'', {'retry-after': '2'}), (201, b'{"id": "x"}', {})])
    out = api.Client(FakeModule()).request('POST', '/api/v1/teams', body=dict(name='a'))
    assert out == {'id': 'x'}
    assert sent[1] == {'slept': 2}
    assert sent[0]['headers']['Idempotency-Key'] == sent[2]['headers']['Idempotency-Key']
    assert sent[0]['headers']['Authorization'] == 'Bearer t'
    assert json.loads(sent[0]['data']) == {'name': 'a'}


def test_if_match_header(calls):
    sent, answers = calls
    answers.append((200, b'{}', {}))
    api.Client(FakeModule()).request('PATCH', '/api/v1/endpoints/e', body={}, if_match=7)
    assert sent[0]['headers']['If-Match'] == '"v7"'
    assert 'Idempotency-Key' not in sent[0]['headers']


def test_problem_detail_becomes_error(calls):
    answers = calls[1]
    problem = dict(status=409, title='Conflict', detail='team is in use', request_id='req_1')
    answers.append((409, json.dumps(problem).encode(), {}))
    with pytest.raises(api.APIError) as e:
        api.Client(FakeModule()).request('DELETE', '/api/v1/teams/a')
    assert e.value.status == 409
    assert str(e.value) == 'certloom API 409: team is in use (request req_1)'


def test_retry_gives_up(calls):
    sent, answers = calls
    answers.extend([(429, b'', {})] * 4)
    with pytest.raises(api.APIError) as e:
        api.Client(FakeModule()).request('GET', '/api/v1/teams')
    assert e.value.status == 429
    assert [s['slept'] for s in sent if 'slept' in s] == [1, 2, 4]


def test_retry_after_too_long_is_not_waited(calls):
    sent, answers = calls
    answers.append((503, b'', {'retry-after': '120'}))
    with pytest.raises(api.APIError):
        api.Client(FakeModule()).request('GET', '/api/v1/teams')
    assert not [s for s in sent if 'slept' in s]


def test_get_returns_none_on_404(calls):
    answers = calls[1]
    answers.append((404, b'{"status": 404, "title": "Not Found"}', {}))
    assert api.Client(FakeModule()).get('/api/v1/teams/missing') is None


def test_query_and_ref_escaping(calls):
    sent, answers = calls
    answers.append((200, b'{}', {}))
    api.Client(FakeModule()).request('PUT', '/api/v1/teams/' + api.ref('a/b c'), raw='x: 1', query=dict(dry_run='true'))
    assert sent[0]['url'] == 'https://certloom.example.test/api/v1/teams/a%2Fb%20c?dry_run=true'
    assert sent[0]['headers']['Content-Type'] == 'application/yaml'


def test_missing_token_fails():
    m = FakeModule(token=None)
    with pytest.raises(SystemExit):
        api.Client(m)
    assert 'CERTLOOM_TOKEN' in m.failed['msg']


def test_changes_ignores_unset_options():
    current = dict(contact='a', enabled=True, interval_seconds=60)
    assert api.changes(current, dict(contact=None, enabled=False, interval_seconds=60)) == ['enabled']
    assert api.changes(current, dict(contact='a')) == []

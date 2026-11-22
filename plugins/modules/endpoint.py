#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: endpoint
short_description: Manage TLS endpoints that certloom probes
version_added: 0.1.0
description:
  - Register, update or remove a TLS endpoint. The endpoint is identified by
    I(host), I(port) and I(sni), which cannot change.
  - Options left out keep their current value.
options:
  host:
    description: Host name or IP address to connect to.
    type: str
    required: true
  port:
    description: TCP port.
    type: int
    default: 443
  sni:
    description: Server name to send in the TLS handshake, if different from I(host).
    type: str
    default: ''
  scope:
    description:
      - Probe scope (id or name) that must allow I(host) and I(port).
      - Required when the endpoint is created.
    type: str
  team:
    description: Owning team (id or name). An empty string removes the owner.
    type: str
  lineage:
    description: Certificate lineage (id or name) the endpoint is expected to serve. An empty string clears it.
    type: str
  interval_seconds:
    description: Seconds between probes. The server default is six hours.
    type: int
  enabled:
    description: Whether the endpoint is probed.
    type: bool
  state:
    description: Whether the endpoint should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - alexandrosnt.certloom.auth
  - alexandrosnt.certloom.auth.attributes
notes:
  - An endpoint that a deployment uses for verification cannot be deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Probe the shop front end
  alexandrosnt.certloom.endpoint:
    host: shop.example.com
    scope: public-web
    team: platform
    interval_seconds: 3600
'''

RETURN = r'''
endpoint:
  description: The endpoint after the task; empty when deleted.
  returned: always
  type: dict
  sample: {id: ep_01..., host: shop.example.com, port: 443, scope_id: scope_01..., enabled: true, version: 2}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.alexandrosnt.certloom.plugins.module_utils import api


def resolve(client, kind, value):
    """Return the id for an id or name; '' stays '' (clears the field)."""
    if not value:
        return value
    obj = client.get('/api/v1/%s/%s' % (kind, api.ref(value)))
    if obj is None:
        raise api.APIError(404, detail='%s %r not found' % (kind[:-1], value))
    return obj['id']


def find(client, host, port, sni):
    for e in client.list('/api/v1/endpoints'):
        if e['host'] == host and e['port'] == port and (e.get('sni') or '') == sni:
            return e
    return None


def ensure(module, client):
    p = module.params
    current = find(client, p['host'], p['port'], p['sni'])
    res = api.Result(module, 'endpoint', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, '/api/v1/endpoints/' + api.ref(current['id']))
        res.exit()

    scope = resolve(client, 'scopes', p['scope'])
    team = None if p['team'] is None else resolve(client, 'teams', p['team'])
    lineage = None if p['lineage'] is None else resolve(client, 'lineages', p['lineage'])

    if current is None:
        if not scope:
            module.fail_json(msg='scope is required to create an endpoint')
        body = dict(host=p['host'], port=p['port'], sni=p['sni'], scope=scope)
        for k, v in (('team', team), ('lineage', lineage), ('interval_seconds', p['interval_seconds'])):
            if v:
                body[k] = v
        preview = dict(host=p['host'], port=p['port'], sni=p['sni'], scope_id=scope, team_id=team or None,
                       lineage_id=lineage or None, interval_seconds=p['interval_seconds'], enabled=True)
        res.create(client, '/api/v1/endpoints', body, preview=preview)
        if p['enabled'] is False:
            res.update(client, '/api/v1/endpoints/' + api.ref(res.obj.get('id', '')), dict(enabled=False),
                       if_match=res.obj.get('version'))
        res.exit()

    # Compare in the response's terms (ids, null for unset); send in the
    # request's terms (team and lineage take '' to clear).
    have = dict(scope=current.get('scope_id'), team=current.get('team_id') or '',
                lineage=current.get('lineage_id') or '', interval_seconds=current.get('interval_seconds'),
                enabled=current.get('enabled'))
    want = dict(scope=scope, team=team, lineage=lineage, interval_seconds=p['interval_seconds'], enabled=p['enabled'])
    changed = api.changes(have, want)
    if changed:
        body = dict((k, want[k]) for k in changed)
        preview = dict((k, v) for k, v in body.items() if k in ('interval_seconds', 'enabled'))
        for k in ('scope', 'team', 'lineage'):
            if k in body:
                preview[k + '_id'] = body[k] or None
        res.update(client, '/api/v1/endpoints/' + api.ref(current['id']), body,
                   if_match=current.get('version'), preview=preview)
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            host=dict(type='str', required=True),
            port=dict(type='int', default=443),
            sni=dict(type='str', default=''),
            scope=dict(type='str'),
            team=dict(type='str'),
            lineage=dict(type='str'),
            interval_seconds=dict(type='int'),
            enabled=dict(type='bool'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: dns_solver
short_description: Manage central certloom DNS-01 solvers
version_added: 0.1.0
description:
  - Create or delete a DNS solver that agents use to answer ACME DNS-01
    challenges for the listed zones, set its credential and choose which
    agents may use it.
  - With I(credential=stored) the DNS provider credential is passed in
    I(secret). certloom seals it to each assigned agent; it is never returned,
    so it cannot be compared. See I(update_secret).
  - With I(credential=ambient) (plugins only) the agent uses its host's own
    cloud identity and no secret is sent.
  - Only the secret and the agent assignments can change. Any other difference
    fails the task; delete the solver and create it again.
options:
  name:
    description: Solver name, unique in the organization.
    type: str
    required: true
  provider:
    description: C(rfc2136), C(cloudflare) or C(plugin). Required when the solver is created.
    type: str
    choices: [rfc2136, cloudflare, plugin]
  plugin:
    description: Absolute path of the solver plugin on the agent hosts (I(provider=plugin) only).
    type: str
  plugin_sha256:
    description: Hex SHA-256 of the plugin binary; agents refuse a plugin that does not match.
    type: str
  zones:
    description: DNS zones the solver may write, lowercase without a trailing dot. Required when the solver is created.
    type: list
    elements: str
  config:
    description: Non-secret provider settings, for example the RFC 2136 C(nameserver) as C(host:port).
    type: dict
  credential:
    description: C(stored) (secret in I(secret)) or C(ambient) (the agent host's identity; plugins only). A new solver uses C(stored) if this is left out.
    type: str
    choices: [stored, ambient]
  secret:
    description:
      - "Provider credential as a dictionary of strings, for example C({api_token: ...})
        for Cloudflare or C({tsig_key: ...}) with the BIND key file contents for RFC 2136."
      - Required when a solver with I(credential=stored) is created.
    type: dict
  update_secret:
    description:
      - When to send I(secret) to an existing solver. C(on_create) never does,
        so a second run reports no change. C(always) sends it on every run,
        which always reports a change; use it for a rotation run.
    type: str
    choices: [on_create, always]
    default: on_create
  agents:
    description:
      - Agents (id or name) allowed to use this solver. The list replaces the
        current assignments. Left out, assignments are not changed.
    type: list
    elements: str
  state:
    description: Whether the solver should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - alexandrosnt.certloom.auth
  - alexandrosnt.certloom.auth.attributes
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Cloudflare for example.com
  alexandrosnt.certloom.dns_solver:
    name: cloudflare-example
    provider: cloudflare
    zones: [example.com]
    secret:
      api_token: "{{ vault_cloudflare_dns_token }}"
    agents: [web-01, web-02]

- name: Rotate the token
  alexandrosnt.certloom.dns_solver:
    name: cloudflare-example
    secret:
      api_token: "{{ vault_cloudflare_dns_token_new }}"
    update_secret: always
'''

RETURN = r'''
dns_solver:
  description: The solver after the task, without the secret; empty when deleted.
  returned: always
  type: dict
  sample: {id: dns_01..., name: cloudflare-example, provider: cloudflare, zones: [example.com], credential: stored, has_secret: true, agents: [agt_01...]}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.alexandrosnt.certloom.plugins.module_utils import api

FIXED = ('provider', 'plugin', 'plugin_sha256', 'zones', 'config', 'credential')


def agent_ids(module, client, refs):
    agents = client.list('/api/v1/agents')
    out = []
    for r in refs:
        match = [a['id'] for a in agents if r in (a['id'], a['name'])]
        if len(match) != 1:
            module.fail_json(msg='agent %s %s' % (r, 'not found' if not match else 'is ambiguous; use its id'))
        out.append(match[0])
    return sorted(set(out))


def fixed_differences(p, current):
    have = dict(provider=current.get('provider'), plugin=current.get('plugin') or '',
                plugin_sha256=current.get('plugin_sha256') or '', zones=sorted(current.get('zones') or []),
                config=current.get('config') or {}, credential=current.get('credential'))
    want = dict((k, p[k]) for k in FIXED)
    if want['zones'] is not None:
        want['zones'] = sorted(want['zones'])
    return api.changes(have, want)


def ensure(module, client):
    p = module.params
    path = '/api/v1/dns-solvers/' + api.ref(p['name'])
    current = client.get(path)
    res = api.Result(module, 'dns_solver', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    want_agents = None if p['agents'] is None else agent_ids(module, client, p['agents'])

    if current is None:
        if not p['provider'] or not p['zones']:
            module.fail_json(msg='provider and zones are required to create a DNS solver')
        credential = p['credential'] or 'stored'
        if credential == 'stored' and not p['secret']:
            module.fail_json(msg='secret is required to create a solver with credential=stored')
        body = dict(name=p['name'], provider=p['provider'], zones=p['zones'], credential=credential)
        for k in ('plugin', 'plugin_sha256', 'config'):
            if p[k]:
                body[k] = p[k]
        preview = dict(body, has_secret=bool(p['secret']), agents=[])
        if p['secret']:
            body['secret'] = p['secret']
        res.create(client, '/api/v1/dns-solvers', body, preview=preview)
        have_agents = []
    else:
        diff = fixed_differences(p, current)
        if diff:
            module.fail_json(msg='DNS solver %s: %s cannot change; delete the solver and create it again'
                             % (p['name'], ', '.join(diff)))
        if p['secret'] and p['update_secret'] == 'always':
            res.update(client, path + '/secret', dict(secret=p['secret']), method='PUT',
                       preview=dict(has_secret=True))
        have_agents = sorted(current.get('agents') or [])

    if want_agents is not None and want_agents != have_agents:
        res.changed = True
        if not module.check_mode:
            sid = api.ref(res.obj['id'])
            for a in want_agents:
                if a not in have_agents:
                    client.request('PUT', '/api/v1/dns-solvers/%s/agents/%s' % (sid, api.ref(a)))
            for a in have_agents:
                if a not in want_agents:
                    client.delete('/api/v1/dns-solvers/%s/agents/%s' % (sid, api.ref(a)))
        res.obj = dict(res.obj, agents=want_agents)
    if res.changed and not module.check_mode:
        res.obj = client.get('/api/v1/dns-solvers/' + api.ref(res.obj['id'])) or res.obj
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            provider=dict(type='str', choices=['rfc2136', 'cloudflare', 'plugin']),
            plugin=dict(type='str'),
            plugin_sha256=dict(type='str'),
            zones=dict(type='list', elements='str'),
            config=dict(type='dict'),
            credential=dict(type='str', choices=['stored', 'ambient']),
            secret=dict(type='dict', no_log=True),
            update_secret=dict(type='str', choices=['on_create', 'always'], default='on_create'),
            agents=dict(type='list', elements='str'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

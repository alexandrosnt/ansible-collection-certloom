#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: scope
short_description: Manage certloom probe scopes
version_added: 0.1.0
description:
  - Create, update or delete a probe scope. A scope limits which hosts and
    ports the TLS prober may connect to.
  - Options left out keep their current value. Loopback, private and link-local
    addresses are refused unless allowed here.
options:
  name:
    description: Scope name, unique in the organization.
    type: str
    required: true
  allow_cidrs:
    description: Address ranges the prober may connect to.
    type: list
    elements: str
  allow_hosts:
    description: Host names the prober may connect to. C(*.example.com) matches subdomains.
    type: list
    elements: str
  allow_loopback:
    description: Allow loopback addresses.
    type: bool
  allow_private:
    description: Allow private (RFC 1918 and ULA) addresses.
    type: bool
  allow_link_local:
    description: Allow link-local addresses.
    type: bool
  ports:
    description: Ports the prober may connect to. Empty allows any port.
    type: list
    elements: int
  state:
    description: Whether the scope should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - certloom.certloom.auth
  - certloom.certloom.auth.attributes
notes:
  - A scope that endpoints still use cannot be deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Internal web servers
  certloom.certloom.scope:
    name: internal-web
    allow_cidrs: [10.20.0.0/16]
    allow_private: true
    ports: [443, 8443]
'''

RETURN = r'''
scope:
  description: The scope after the task; empty when deleted.
  returned: always
  type: dict
  sample: {id: scope_01..., name: internal-web, enabled: true, config: {allow_cidrs: [10.20.0.0/16], allow_private: true, ports: [443]}}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api

CONFIG_KEYS = ('allow_cidrs', 'allow_hosts', 'allow_loopback', 'allow_private', 'allow_link_local', 'ports')


def normalize(config):
    # The API leaves out false and empty values; compare the same way.
    return dict((k, config[k]) for k in CONFIG_KEYS if config.get(k))


def ensure(module, client):
    p = module.params
    path = '/api/v1/scopes/' + api.ref(p['name'])
    current = client.get(path)
    res = api.Result(module, 'scope', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    have = normalize((current or {}).get('config') or {})
    want = dict(have)
    for k in CONFIG_KEYS:
        if p[k] is not None:
            want[k] = p[k]
    want = normalize(want)

    if current is None:
        res.create(client, '/api/v1/scopes', dict(name=p['name'], config=want),
                   preview=dict(name=p['name'], config=want, enabled=True))
    elif want != have:
        res.update(client, path, dict(config=want))
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            allow_cidrs=dict(type='list', elements='str'),
            allow_hosts=dict(type='list', elements='str'),
            allow_loopback=dict(type='bool'),
            allow_private=dict(type='bool'),
            allow_link_local=dict(type='bool'),
            ports=dict(type='list', elements='int'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

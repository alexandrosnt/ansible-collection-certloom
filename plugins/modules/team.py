#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: team
short_description: Manage certloom teams
version_added: 0.1.0
description:
  - Create, update or delete a team. Teams own certificate lineages and endpoints.
options:
  name:
    description: Team name, unique in the organization.
    type: str
    required: true
  contact:
    description: How to reach the team, such as an email address or chat channel.
    type: str
  state:
    description: Whether the team should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - certloom.certloom.auth
  - certloom.certloom.auth.attributes
notes:
  - A team that still owns lineages or endpoints cannot be deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Platform team
  certloom.certloom.team:
    name: platform
    contact: platform@example.com
'''

RETURN = r'''
team:
  description: The team after the task; empty when deleted.
  returned: always
  type: dict
  sample: {id: 8d0c..., name: platform, contact: platform@example.com}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def ensure(module, client):
    p = module.params
    path = '/api/v1/teams/' + api.ref(p['name'])
    current = client.get(path)
    res = api.Result(module, 'team', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    if current is None:
        res.create(client, '/api/v1/teams', dict(name=p['name'], contact=p['contact'] or ''))
        res.exit()

    changed = api.changes(current, dict(contact=p['contact']))
    if changed:
        res.update(client, path, dict((k, p[k]) for k in changed))
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            contact=dict(type='str'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: channel
short_description: Manage certloom notification channels
version_added: 0.1.0
description:
  - Create, update or delete a notification channel (webhook or email).
  - A channel never holds a secret. I(credential_ref) names where the server
    finds one, such as C(env:CERTLOOM_WEBHOOK_SECRET) or C(file:/run/secrets/smtp).
  - Options left out keep their current value. I(config) replaces the whole
    configuration when given.
options:
  name:
    description: Channel name, unique in the organization.
    type: str
    required: true
  kind:
    description:
      - C(webhook) or C(email). Required when the channel is created; it cannot
        change afterwards.
    type: str
    choices: [webhook, email]
  config:
    description:
      - Settings for the kind. Webhook - C(url), optional C(allow_private).
        Email - C(host), C(port), C(from), C(to) (list).
      - Required when the channel is created.
    type: dict
  credential_ref:
    description: Reference to the webhook signing secret or SMTP password on the server.
    type: str
  min_severity:
    description: Lowest finding severity sent to this channel.
    type: str
    choices: [info, warning, critical]
  enabled:
    description: Whether notifications are sent.
    type: bool
  state:
    description: Whether the channel should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - certloom.certloom.auth
  - certloom.certloom.auth.attributes
notes:
  - A channel named in the active policy cannot be renamed or deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Alerts to the on-call webhook
  certloom.certloom.channel:
    name: oncall
    kind: webhook
    config:
      url: https://hooks.example.com/certloom
    credential_ref: env:CERTLOOM_ONCALL_SECRET
    min_severity: warning
'''

RETURN = r'''
channel:
  description: The channel after the task; empty when deleted.
  returned: always
  type: dict
  sample: {id: ch_01..., name: oncall, kind: webhook, config: {url: https://hooks.example.com/certloom}, min_severity: warning, enabled: true}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def ensure(module, client):
    p = module.params
    current = None
    for c in client.list('/api/v1/channels'):
        if c['name'] == p['name']:
            current = c
    res = api.Result(module, 'channel', current)
    path = '/api/v1/channels/' + api.ref(current['id']) if current else None

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    if current is None:
        if not p['kind'] or p['config'] is None:
            module.fail_json(msg='kind and config are required to create a channel')
        body = dict(name=p['name'], kind=p['kind'], config=p['config'])
        for k in ('credential_ref', 'min_severity'):
            if p[k]:
                body[k] = p[k]
        res.create(client, '/api/v1/channels', body, preview=dict(body, enabled=True))
        if p['enabled'] is False:
            res.update(client, '/api/v1/channels/' + api.ref(res.obj.get('id', '')), dict(enabled=False))
        res.exit()

    if p['kind'] and p['kind'] != current['kind']:
        module.fail_json(msg='channel %s is a %s channel; the kind cannot change, delete it first'
                         % (p['name'], current['kind']))
    have = dict(current, credential_ref=current.get('credential_ref') or '')
    changed = api.changes(have, dict(config=p['config'], credential_ref=p['credential_ref'],
                                     min_severity=p['min_severity'], enabled=p['enabled']))
    if changed:
        res.update(client, path, dict((k, p[k]) for k in changed))
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            kind=dict(type='str', choices=['webhook', 'email']),
            config=dict(type='dict'),
            credential_ref=dict(type='str'),
            min_severity=dict(type='str', choices=['info', 'warning', 'critical']),
            enabled=dict(type='bool'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

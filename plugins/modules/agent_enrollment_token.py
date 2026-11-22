#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: agent_enrollment_token
short_description: Create a one-time certloom agent enrollment token
version_added: 0.1.0
description:
  - Create a single-use token that enrolls one certloom-agent, and return it
    with the hash of the agent CA that the agent must pin.
  - "The token is a secret. Ansible cannot hide one return value from the log
    without also hiding it from the playbook, so B(always set) C(no_log: true)
    on the task. The R(certloom.certloom.agent role,ansible_collections.certloom.certloom.agent_role) does this for you."
  - Every run creates a new token, so the task always reports a change.
    Unused tokens expire after I(ttl_seconds).
options:
  name:
    description: Name hint for the agent that enrolls with the token.
    type: str
  ttl_seconds:
    description: Seconds until the token expires, at most 3600.
    type: int
    default: 900
extends_documentation_fragment:
  - certloom.certloom.auth
attributes:
  check_mode:
    support: full
    description: Reports a change without creating a token.
  diff_mode:
    support: none
    description: Nothing to compare.
notes:
  - Needs the owner role.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Token for this host
  certloom.certloom.agent_enrollment_token:
    name: "{{ inventory_hostname }}"
  delegate_to: localhost
  register: enroll
  no_log: true
'''

RETURN = r'''
token:
  description: The enrollment token. Feed it to C(certloom-agent enroll) on stdin.
  returned: changed and not check mode
  type: str
ca_hash:
  description: Hash of the agent CA to pass as C(--ca-hash).
  returned: changed and not check mode
  type: str
  sample: sha256:3f1c...
expires_at:
  description: When the token expires.
  returned: changed and not check mode
  type: str
id:
  description: Token id, as shown in the audit log.
  returned: changed and not check mode
  type: str
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def create(module, client):
    if module.check_mode:
        module.exit_json(changed=True)
    body = dict(ttl_seconds=module.params['ttl_seconds'])
    if module.params['name']:
        body['name'] = module.params['name']
    t = client.request('POST', '/api/v1/agents/enrollment-tokens', body=body)
    module.exit_json(changed=True, token=t['token'], ca_hash=t['ca_hash'], expires_at=t['expires_at'], id=t['id'])


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str'),
            ttl_seconds=dict(type='int', default=900),
        ),
        supports_check_mode=True,
    )
    if not 0 < module.params['ttl_seconds'] <= 3600:
        module.fail_json(msg='ttl_seconds must be between 1 and 3600')
    api.run(module, lambda client: create(module, client))


if __name__ == '__main__':
    main()

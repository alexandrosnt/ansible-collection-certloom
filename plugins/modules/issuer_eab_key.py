#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: issuer_eab_key
short_description: Manage single-use EAB keys of a certloom issuer
version_added: 0.1.0
description:
  - Add a single-use external account binding key to an issuer's pool, or
    remove one. Each key registers one agent's ACME account and is then
    consumed.
  - The issuer must use C(eab_mode=single_use), see M(alexandrosnt.certloom.issuer).
  - A key that exists is left as it is. The HMAC key is never returned, so a
    key with the same I(kid) is not compared or replaced.
options:
  issuer:
    description: Issuer id or name.
    type: str
    required: true
  kid:
    description: EAB key ID from the CA.
    type: str
    required: true
  hmac:
    description: EAB HMAC key (base64url). Required to add a key.
    type: str
  expires_at:
    description: When the CA expires the key, as an RFC 3339 timestamp. Used for the pool-low warning.
    type: str
  state:
    description:
      - Whether the key should be in the pool. Only available or failed keys can
        be removed; claimed and consumed keys stay for the audit trail.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - alexandrosnt.certloom.auth
  - alexandrosnt.certloom.auth.attributes
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Fill the EAB pool
  alexandrosnt.certloom.issuer_eab_key:
    issuer: commercial
    kid: "{{ item.kid }}"
    hmac: "{{ item.hmac }}"
  loop: "{{ eab_keys }}"
  loop_control:
    label: "{{ item.kid }}"
'''

RETURN = r'''
key:
  description: The key after the task, without the HMAC; empty when removed.
  returned: always
  type: dict
  sample: {id: eab_01..., kid: kid-123, state: available}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.alexandrosnt.certloom.plugins.module_utils import api


def ensure(module, client):
    p = module.params
    issuer = client.get('/api/v1/issuers/' + api.ref(p['issuer']))
    if issuer is None:
        module.fail_json(msg='issuer %s not found' % p['issuer'])
    keys = '/api/v1/issuers/%s/eab-keys' % api.ref(issuer['id'])
    current = None
    for k in client.list(keys):
        if k['kid'] == p['kid']:
            current = k
    res = api.Result(module, 'key', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, keys + '/' + api.ref(current['id']))
        res.exit()

    if current is None:
        if not p['hmac']:
            module.fail_json(msg='hmac is required to add a key')
        body = dict(kid=p['kid'], hmac=p['hmac'])
        if p['expires_at']:
            body['expires_at'] = p['expires_at']
        preview = dict(issuer_id=issuer['id'], kid=p['kid'], expires_at=p['expires_at'], state='available')
        res.create(client, keys, body, preview=preview)
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            issuer=dict(type='str', required=True),
            kid=dict(type='str', required=True),
            hmac=dict(type='str', no_log=True),
            expires_at=dict(type='str'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

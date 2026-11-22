#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: issuer
short_description: Manage certloom ACME issuers
version_added: 0.1.0
description:
  - Create, update or delete an ACME issuer (a CA directory and account settings).
  - Options left out keep their current value.
  - The EAB HMAC key is sent to the server, sealed there and never returned, so
    it cannot be compared. See I(update_secret).
options:
  name:
    description: Issuer name, unique in the organization.
    type: str
    required: true
  directory_url:
    description:
      - ACME directory URL of the CA. Required when the issuer is created; it
        cannot change afterwards.
    type: str
  email:
    description: Contact email for the ACME account.
    type: str
  agree_tos:
    description:
      - Records that you accept the CA's terms of service. Must be C(true) to
        create the issuer.
    type: bool
  profile:
    description: ACME certificate profile to request, if the CA offers profiles.
    type: str
  eab_mode:
    description:
      - External account binding. C(none), C(reusable) (one key ID and HMAC for
        every account) or C(single_use) (a pool of keys managed with
        M(certloom.certloom.issuer_eab_key)).
    type: str
    choices: [none, reusable, single_use]
  eab_kid:
    description: EAB key ID from the CA, for I(eab_mode=reusable).
    type: str
  eab_hmac:
    description:
      - EAB HMAC key as the CA shows it (base64url), for I(eab_mode=reusable).
    type: str
  update_secret:
    description:
      - When to send I(eab_hmac). C(on_create) sends it only when EAB is set up
        or its key ID changes, so a second run reports no change. C(always)
        sends it on every run, which always reports a change.
    type: str
    choices: [on_create, always]
    default: on_create
  state:
    description: Whether the issuer should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - certloom.certloom.auth
  - certloom.certloom.auth.attributes
notes:
  - An issuer that deployments or EAB keys still use cannot be deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Let's Encrypt
  certloom.certloom.issuer:
    name: letsencrypt
    directory_url: https://acme-v02.api.letsencrypt.org/directory
    email: pki@example.com
    agree_tos: true

- name: Commercial CA with EAB
  certloom.certloom.issuer:
    name: commercial
    directory_url: https://acme.example-ca.com/directory
    agree_tos: true
    eab_mode: reusable
    eab_kid: "{{ ca_eab_kid }}"
    eab_hmac: "{{ ca_eab_hmac }}"
'''

RETURN = r'''
issuer:
  description: The issuer after the task; empty when deleted. Never contains the HMAC key.
  returned: always
  type: dict
  sample: {id: iss_01..., name: letsencrypt, kind: acme, directory_url: https://acme-v02.api.letsencrypt.org/directory, eab_mode: none}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def eab_body(module, current):
    """Return the body for PUT .../eab, or None if EAB needs no change."""
    p = module.params
    mode = p['eab_mode']
    if mode is None:
        return None
    if mode != 'reusable':
        if current.get('eab_mode', 'none') == mode:
            return None
        return dict(mode=mode, kid='', hmac='')
    if not p['eab_kid']:
        module.fail_json(msg='eab_kid is required with eab_mode=reusable')
    setup = (current.get('eab_mode') != 'reusable' or current.get('eab_kid') != p['eab_kid']
             or not current.get('has_eab_hmac'))
    if not setup and p['update_secret'] != 'always':
        return None
    if not p['eab_hmac']:
        module.fail_json(msg='eab_hmac is required to set up or change reusable EAB')
    return dict(mode=mode, kid=p['eab_kid'], hmac=p['eab_hmac'])


def ensure(module, client):
    p = module.params
    path = '/api/v1/issuers/' + api.ref(p['name'])
    current = client.get(path)
    res = api.Result(module, 'issuer', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    if current is None:
        if not p['directory_url']:
            module.fail_json(msg='directory_url is required to create an issuer')
        if not p['agree_tos']:
            module.fail_json(msg="agree_tos must be true to create an issuer (it records that you accept the CA's terms)")
        body = dict(name=p['name'], directory_url=p['directory_url'], agree_tos=True)
        for k in ('email', 'profile'):
            if p[k]:
                body[k] = p[k]
        res.create(client, '/api/v1/issuers', body, preview=dict(body, kind='acme', eab_mode='none'))
    else:
        if p['directory_url'] and p['directory_url'] != current['directory_url']:
            module.fail_json(msg='the directory URL of issuer %s cannot change; create a new issuer' % p['name'])
        have = dict(current, email=current.get('email') or '', profile=current.get('profile') or '')
        changed = api.changes(have, dict(email=p['email'], profile=p['profile']))
        if changed:
            res.update(client, path, dict((k, p[k]) for k in changed))

    body = eab_body(module, res.obj)
    if body:
        res.update(client, path + '/eab', body, method='PUT',
                   preview=dict(eab_mode=body['mode'], eab_kid=body['kid'], has_eab_hmac=bool(body['hmac'])))
    res.exit()


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            directory_url=dict(type='str'),
            email=dict(type='str'),
            agree_tos=dict(type='bool'),
            profile=dict(type='str'),
            eab_mode=dict(type='str', choices=['none', 'reusable', 'single_use']),
            eab_kid=dict(type='str'),
            eab_hmac=dict(type='str', no_log=True),
            update_secret=dict(type='str', choices=['on_create', 'always'], default='on_create'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

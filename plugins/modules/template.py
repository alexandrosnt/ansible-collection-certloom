#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: template
short_description: Manage certloom certificate templates
version_added: 0.1.0
description:
  - Create, update or delete a certificate template. Templates are versioned
    documents; deployments that use a template follow its latest version.
  - The server plans every change first. A change that existing deployments
    would violate fails the task and lists the violations. A change that
    needs new approvals is applied and the approvals are requested.
  - A second run with the same document reports no change, because the module
    compares the server's parsed form of both documents.
options:
  name:
    description: Template name. Must match C(metadata.name) in I(document).
    type: str
    required: true
  document:
    description:
      - The template as a dictionary, or as YAML or JSON text (for example from
        C(lookup('file', 'web.yaml'))). Required with I(state=present).
    type: raw
  state:
    description: Whether the template should exist.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - certloom.certloom.auth
  - certloom.certloom.auth.attributes
notes:
  - A template that deployments still use cannot be deleted.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Web server template
  certloom.certloom.template:
    name: web
    document: "{{ lookup('file', 'templates/web.yaml') }}"
'''

RETURN = r'''
template:
  description: The template after the task; empty when deleted.
  returned: always
  type: dict
plan:
  description: The server's plan for the document (changed deployments, approvals needed, violations).
  returned: when I(state=present)
  type: dict
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def source(module):
    doc = module.params['document']
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        named = (doc.get('metadata') or {}).get('name')
        if named and named != module.params['name']:
            module.fail_json(msg='document metadata.name is %s, not %s' % (named, module.params['name']))
        return json.dumps(doc)
    module.fail_json(msg='document must be a dictionary or YAML text')


def ensure(module, client):
    p = module.params
    path = '/api/v1/templates/' + api.ref(p['name'])
    current = client.get(path)
    res = api.Result(module, 'template', current)

    if p['state'] == 'absent':
        if current:
            res.delete(client, path)
        res.exit()

    if p['document'] is None:
        module.fail_json(msg='document is required with state=present')
    src = source(module)
    plan = client.request('PUT', '/api/v1/templates', raw=src, query=dict(dry_run='true'))
    if plan.get('name') != p['name']:
        module.fail_json(msg='document metadata.name is %s, not %s' % (plan.get('name'), p['name']))
    if plan.get('violations'):
        module.fail_json(msg='existing deployments would violate this template', violations=plan['violations'])
    if current is None or current.get('document') != plan.get('document'):
        res.changed = True
        if module.check_mode:
            res.obj = dict(current or {}, name=p['name'], document=plan.get('document'))
        else:
            plan = client.request('PUT', '/api/v1/templates', raw=src)
            res.obj = client.get(path) or {}
    res.exit(plan=plan)


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            name=dict(type='str', required=True),
            document=dict(type='raw'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

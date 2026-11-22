#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: policy
short_description: Apply the certloom monitoring policy
version_added: 0.1.0
description:
  - Apply a policy document (checks, thresholds, approvals, channels) as a new
    policy version.
  - The server plans every change first; the plan, with how many certificates
    change severity, is returned. A second run with the same document reports
    no change, because the module compares the server's parsed form of both
    documents.
options:
  document:
    description:
      - The policy as a dictionary, or as YAML or JSON text (for example from
        C(lookup('file', 'policy.yaml'))).
    type: raw
    required: true
extends_documentation_fragment:
  - alexandrosnt.certloom.auth
  - alexandrosnt.certloom.auth.attributes
notes:
  - There is one policy per organization, so there is no I(state=absent).
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Monitoring policy
  alexandrosnt.certloom.policy:
    document: "{{ lookup('file', 'policy.yaml') }}"
'''

RETURN = r'''
policy:
  description: The active policy after the task.
  returned: always
  type: dict
plan:
  description: The server's plan for the document.
  returned: always
  type: dict
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.alexandrosnt.certloom.plugins.module_utils import api


def ensure(module, client):
    doc = module.params['document']
    if isinstance(doc, dict):
        src = json.dumps(doc)
    elif isinstance(doc, str):
        src = doc
    else:
        module.fail_json(msg='document must be a dictionary or YAML text')
    current = client.request('GET', '/api/v1/policy')
    res = api.Result(module, 'policy', current)
    plan = client.request('PUT', '/api/v1/policy', raw=src, query=dict(dry_run='true'))
    if current.get('document') != plan.get('document'):
        res.changed = True
        if module.check_mode:
            res.obj = dict(current, document=plan.get('document'))
        else:
            plan = client.request('PUT', '/api/v1/policy', raw=src)
            res.obj = client.request('GET', '/api/v1/policy')
    res.exit(plan=plan)


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(
            document=dict(type='raw', required=True),
        ),
        supports_check_mode=True,
    )
    api.run(module, lambda client: ensure(module, client))


if __name__ == '__main__':
    main()

#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: issuer_info
short_description: List certloom ACME issuers
version_added: 0.1.0
description:
  - Return all ACME issuers, or the one with the given name or id.
options:
  name:
    description: Return only the issuer with this name or id.
    type: str
extends_documentation_fragment:
  - certloom.certloom.auth
attributes:
  check_mode:
    support: full
    description: Read-only; runs the same in check mode.
  diff_mode:
    support: none
    description: Nothing to compare.
author: certloom maintainers (@alexandrosnt)
'''

EXAMPLES = r'''
- name: Look up issuer
  certloom.certloom.issuer_info:
    name: letsencrypt
  register: found
'''

RETURN = r'''
issuers:
  description: Matching ACME issuers; empty if none match.
  returned: always
  type: list
  elements: dict
  sample: [{id: iss_01..., name: letsencrypt, kind: acme, eab_mode: none}]
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.certloom.certloom.plugins.module_utils import api


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(name=dict(type='str')),
        supports_check_mode=True,
    )
    api.run_info(module, '/api/v1/issuers', 'issuers')


if __name__ == '__main__':
    main()

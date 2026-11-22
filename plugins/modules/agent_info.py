#!/usr/bin/python
# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: agent_info
short_description: List certloom enrolled agents
version_added: 0.1.0
description:
  - Return all enrolled agents, or the one with the given name or id.
options:
  name:
    description: Return only the agent with this name or id.
    type: str
extends_documentation_fragment:
  - alexandrosnt.certloom.auth
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
- name: Look up agent
  alexandrosnt.certloom.agent_info:
    name: web-01
  register: found
'''

RETURN = r'''
agents:
  description: Matching enrolled agents; empty if none match.
  returned: always
  type: list
  elements: dict
  sample: [{id: agt_01..., name: web-01, state: active, health: active, hostname: web-01, version: 0.1.0}]
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.alexandrosnt.certloom.plugins.module_utils import api


def main():
    module = AnsibleModule(
        argument_spec=api.argument_spec(name=dict(type='str')),
        supports_check_mode=True,
    )
    api.run_info(module, '/api/v1/agents', 'agents')


if __name__ == '__main__':
    main()

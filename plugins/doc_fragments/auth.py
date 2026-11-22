# Copyright (c) certloom contributors
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r'''
options:
  url:
    description:
      - Base URL of the certloom server, for example C(https://certloom.example.com).
      - If not set, the value of the E(CERTLOOM_ENDPOINT) environment variable is used.
    type: str
  token:
    description:
      - API token to authenticate with.
      - If not set, the value of the E(CERTLOOM_TOKEN) environment variable is used.
    type: str
  ca_path:
    description:
      - PEM file with the CA certificates to trust for the server, for a server
        with a certificate from a private CA.
    type: path
  validate_certs:
    description:
      - Verify the server's TLS certificate. Only turn this off for tests.
    type: bool
    default: true
  timeout:
    description:
      - Seconds to wait for each API response.
    type: int
    default: 60
notes:
  - "The modules talk to the certloom API and do not touch the managed host.
    Run them on the controller, for example with C(delegate_to: localhost)
    or in a play against C(localhost)."
'''

    ATTRIBUTES = r'''
attributes:
  check_mode:
    support: full
    description: Reports what would change without changing it.
  diff_mode:
    support: full
    description: Shows the fields that change. Secrets are never included.
'''

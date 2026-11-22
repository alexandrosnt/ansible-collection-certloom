# certloom Ansible collection

Ansible content for [certloom](https://github.com/alexandrosnt/certloom), a
self-hosted certificate lifecycle manager:

- modules that manage certloom's configuration through its REST API, and
- a role that installs, configures and enrolls `certloom-agent` on Linux hosts.

Certificates and private keys are never handled by Ansible. Keys are generated
by the agents and stay on their hosts; this collection only manages what the
agents and the control plane should do.

## Requirements

- ansible-core 2.20 or later.
- A certloom server and an API token. Configuration modules need the
  permissions of the object they manage; creating enrollment tokens needs
  the owner role.
- Nothing to install with pip. The modules use only Ansible's own HTTP code.

## Install

```sh
ansible-galaxy collection install certloom.certloom
```

## Content

| Name | Purpose |
|---|---|
| `team`, `scope`, `endpoint`, `channel` | Teams, probe scopes, TLS endpoints to probe, notification channels |
| `issuer`, `issuer_eab_key` | ACME issuers, including external account binding |
| `dns_solver` | Central DNS-01 solvers and which agents may use them |
| `template`, `policy` | Certificate templates and the monitoring policy (planned on the server first) |
| `agent_enrollment_token` | One-time agent enrollment token |
| `team_info`, `scope_info`, `issuer_info`, `agent_info` | Lookups |
| role `agent` | Install, configure, enroll and start `certloom-agent` |

All modules support check mode and `--diff`, and report no change when the
object already matches. Run them on the controller; they do not touch the
managed host.

## Connecting

Set `CERTLOOM_ENDPOINT` and `CERTLOOM_TOKEN` in the environment, or pass
`url` and `token`. To set them once for all modules, use the action group:

```yaml
- hosts: localhost
  module_defaults:
    group/certloom.certloom.certloom:
      url: https://certloom.example.com
      token: "{{ vault_certloom_token }}"
  tasks:
    - certloom.certloom.team:
        name: platform
        contact: platform@example.com

    - certloom.certloom.scope:
        name: public-web
        allow_hosts: ["*.example.com"]
        ports: [443]

    - certloom.certloom.endpoint:
        host: shop.example.com
        scope: public-web
        team: platform
```

Use `ca_path` when the server's certificate comes from a private CA.

## Secrets

Secrets you pass in (EAB HMAC keys, DNS provider credentials) are marked
`no_log`, sent to the server, sealed there, and never returned. Because they
cannot be read back, they cannot be compared either. Modules that take a
secret have an `update_secret` option:

- `on_create` (default) sends the secret only when the object or its key ID is
  new, so repeated runs report no change;
- `always` sends it on every run, for example in a rotation playbook.

`agent_enrollment_token` returns a token. Always set `no_log: true` on that
task. The `agent` role does this for you.

## Rolling out the agent

```yaml
- hosts: webservers
  become: true
  roles:
    - role: certloom.certloom.agent
      vars:
        certloom_agent_server: https://certloom.example.com:8444
        certloom_agent_package_url: https://downloads.example.com/certloom-agent_1.0.0-1_amd64.deb
        certloom_agent_package_sha256: "<sha256 of the package>"
        certloom_agent_config:
          targets:
            - name: www
              type: nginx
              live_link: /etc/certloom/live/www
              webroot: /var/www/acme
              test_command: [nginx, -t]
              reload_command: [systemctl, reload, nginx]
              verify_address: 127.0.0.1:443
              allowed_sans: [www.example.com]
```

The role installs the `.deb` or `.rpm` (the checksum is required), writes
`/etc/certloom-agent/config.yaml` after checking it with
`certloom-agent check-config`, and, on hosts that are not enrolled yet,
creates a one-time token on the controller and passes it to
`certloom-agent enroll` on stdin. Then it enables and starts the service.
Enrolled hosts are left enrolled; later runs only update the package and the
configuration.

Tested on Debian 13, Ubuntu 24.04 and Rocky Linux 9. Other Debian and Red Hat
family releases with systemd should work. Windows hosts are not covered by the
role yet.

See `ansible-doc -t role certloom.certloom.agent` for all variables.

## Development

Tests run against a throwaway certloom server:

```sh
CERTLOOM_SRC=../certloom scripts/testserver.sh start
ansible-test sanity --docker
ansible-test units --docker
ansible-test integration          # uses tests/integration/integration_config.yml
. .testserver/env && tests/secrets/run.sh
tests/role/run.sh debian path/to/certloom-agent.deb
scripts/testserver.sh stop
```

`ansible-test` expects the collection at
`ansible_collections/certloom/certloom` in a directory on the collections
path.

Changes need a changelog fragment in `changelogs/fragments/`, see
[antsibull-changelog](https://ansible.readthedocs.io/projects/antsibull-changelog/).

## Releasing

1. Set `version` in `galaxy.yml`.
2. `antsibull-changelog release` (writes `CHANGELOG.md` from the fragments).
3. Commit, then tag `vX.Y.Z` and push the tag. The release workflow builds the
   collection, publishes it to Galaxy (repository secret `GALAXY_API_KEY`) and
   creates the GitHub release.

## License

Apache License 2.0, see [LICENSE](LICENSE).

# alexandrosnt.certloom.agent

Installs `certloom-agent` on Debian and Red Hat family hosts, writes its
configuration, enrolls hosts that are not enrolled yet and starts the systemd
service.

## Requirements

- A Debian or Red Hat family host with systemd. Tested on Debian 13,
  Ubuntu 24.04 and Rocky Linux 9. Windows is not covered yet.
- The `certloom-agent` `.deb` or `.rpm` for the host, reachable by URL from the
  host or as a file on the controller, and its SHA-256.
- For enrollment: a certloom API token with the owner role on the controller,
  in `CERTLOOM_TOKEN` or `certloom_agent_api_token`.

## Variables

| Variable | Default | Description |
|---|---|---|
| `certloom_agent_server` | (required) | HTTPS URL of the certloom agent listener |
| `certloom_agent_package_url` | `""` | URL of the package, downloaded on the host |
| `certloom_agent_package_file` | `""` | Package on the controller, used when no URL is set |
| `certloom_agent_package_sha256` | (required) | SHA-256 of the package, hex |
| `certloom_agent_package_gpg_check` | `false` | Check `.rpm` signatures with dnf; packages are not signed yet |
| `certloom_agent_name` | `inventory_hostname` | Agent name shown in certloom |
| `certloom_agent_config` | `{}` | Merged into `config.yaml`: targets, dns_solvers, cloud and so on |
| `certloom_agent_config_path` | `/etc/certloom-agent/config.yaml` | Configuration file |
| `certloom_agent_state_dir` | `/var/lib/certloom-agent` | Agent identity and keys |
| `certloom_agent_enroll` | `true` | Enroll hosts that are not enrolled yet |
| `certloom_agent_api_url` | `CERTLOOM_ENDPOINT` | certloom API URL used to create the token |
| `certloom_agent_api_token` | `CERTLOOM_TOKEN` | certloom API token used to create the token |
| `certloom_agent_api_ca_path` | `""` | CA bundle for the API, if it uses a private CA |
| `certloom_agent_token_ttl` | `900` | Seconds the enrollment token stays valid |
| `certloom_agent_service_enabled` | `true` | Enable and start the service, or stop and disable it |

`ansible-doc -t role alexandrosnt.certloom.agent` shows the same list.

## How enrollment works

On a host without an agent identity the role creates a one-time enrollment
token on the controller with `alexandrosnt.certloom.agent_enrollment_token` and
passes it to `certloom-agent enroll` on stdin, so it never appears on the
command line or in the log. Enrolled hosts stay enrolled; later runs only
update the package and the configuration. The configuration is checked with
`certloom-agent check-config` before it replaces the old file.

## Example

```yaml
- hosts: webservers
  become: true
  roles:
    - role: alexandrosnt.certloom.agent
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

## License

Apache-2.0

#!/bin/sh
# Tests the agent role on systemd containers against the test server
# (scripts/testserver.sh, started with TESTSERVER_LISTEN=0.0.0.0 and
# TESTSERVER_HOST set to a name the containers can reach).
#
#   tests/role/run.sh debian /path/to/certloom-agent.deb
#   tests/role/run.sh rocky /path/to/certloom-agent.rpm
set -eu

# Docker Desktop on Windows (Git Bash) needs native host paths and no path
# rewriting of the container paths.
export MSYS_NO_PATHCONV=1
hostdir() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

distro=$1
package=$2
root=$(cd "$(dirname "$0")/../.." && pwd)
. "$root/.testserver/env"
agent_server=$(printf '%s' "$CERTLOOM_ENDPOINT" | sed -E 's#^http://([^:]+):.*#https://\1:'"${TESTSERVER_AGENT_PORT:-18454}"'#')
name=certloom-role-$distro
image=certloom-role-test:$distro
sha=$(sha256sum "$package" | cut -d' ' -f1)

docker build -q -t "$image" -f "$(hostdir "$root/tests/role")/Dockerfile.$distro" "$(hostdir "$root/tests/role")" >/dev/null
docker rm -f "$name" >/dev/null 2>&1 || true
docker run -d --name "$name" --privileged --cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
	--add-host=host.docker.internal:host-gateway \
	-v "$(hostdir "$root"):/work/ansible_collections/certloom/certloom:ro" -v "$(hostdir "$(dirname "$package")")/$(basename "$package"):/pkg/$(basename "$package"):ro" \
	"$image" >/dev/null
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT

run() {
	docker exec -e ANSIBLE_COLLECTIONS_PATH=/work -e ANSIBLE_FORCE_COLOR=0 \
		-e CERTLOOM_ENDPOINT="$CERTLOOM_ENDPOINT" -e CERTLOOM_TOKEN="$CERTLOOM_TOKEN" \
		-e AGENT_SERVER="$agent_server" -e AGENT_PACKAGE="/pkg/$(basename "$package")" \
		-e AGENT_PACKAGE_SHA256="$sha" -e AGENT_NAME="$name" \
		"$name" /opt/ansible/bin/ansible-playbook -e ansible_python_interpreter=/usr/bin/python3 "$@"
}

dir=/work/ansible_collections/certloom/certloom/tests/role
run "$dir/install.yml"
run "$dir/again.yml" | tee "$root/.testserver/again-$distro.log"
grep -q "changed=0 " "$root/.testserver/again-$distro.log" || {
	echo "second run of the role reported changes" >&2
	exit 1
}
echo "role test passed on $distro"

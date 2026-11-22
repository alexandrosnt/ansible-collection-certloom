#!/bin/sh
# Starts a throwaway certloomd with PostgreSQL for the integration tests. It
# writes CERTLOOM_ENDPOINT and CERTLOOM_TOKEN to .testserver/env and the same
# values to tests/integration/integration_config.yml for ansible-test.
#
#   CERTLOOM_SRC=../certloom scripts/testserver.sh start
#   ansible-test integration
#   scripts/testserver.sh stop
#
# Needs Docker and Go. CERTLOOM_SRC points at a certloom checkout.
#
# TESTSERVER_LISTEN sets the address certloomd listens on (default 127.0.0.1)
# and TESTSERVER_HOST the name clients use to reach it, for example
# 0.0.0.0 and host.docker.internal when ansible runs in a container.
set -eu

dir=$(pwd)/.testserver
pg=certloom-ansible-pg
pgport=${TESTSERVER_PG_PORT:-55440}
apiport=${TESTSERVER_PORT:-18453}
agentport=${TESTSERVER_AGENT_PORT:-18454}
listen=${TESTSERVER_LISTEN:-127.0.0.1}
host=${TESTSERVER_HOST:-127.0.0.1}
owner_pw=test-owner-not-secret
app_pw=test-app-not-secret
config=tests/integration/integration_config.yml

stop() {
	if [ -f "$dir/certloomd.pid" ]; then
		kill "$(cat "$dir/certloomd.pid")" 2>/dev/null || true
	fi
	docker rm -f "$pg" >/dev/null 2>&1 || true
	rm -rf "$dir" "$config"
}

start() {
	: "${CERTLOOM_SRC:?set CERTLOOM_SRC to a certloom checkout}"
	stop
	mkdir -p "$dir"
	bin="$dir/certloomd$(go env GOEXE)"
	# certloom pins its own Go toolchain; let go fetch it for this build.
	(cd "$CERTLOOM_SRC" && GOTOOLCHAIN=auto go build -o "$bin" ./cmd/certloomd)

	docker run -d --name "$pg" -p "127.0.0.1:$pgport:5432" \
		-e POSTGRES_USER=certloom_owner -e POSTGRES_PASSWORD="$owner_pw" -e POSTGRES_DB=certloom \
		postgres:18-alpine >/dev/null
	i=0
	# Check over TCP: the image's first-start init server listens only on the
	# Unix socket and is restarted afterwards.
	until docker exec "$pg" pg_isready -h 127.0.0.1 -U certloom_owner -d certloom >/dev/null 2>&1; do
		i=$((i + 1))
		[ "$i" -lt 60 ] || { echo "postgres did not start" >&2; exit 1; }
		sleep 1
	done

	CERTLOOM_MIGRATE_DATABASE_URL="postgres://certloom_owner:$owner_pw@127.0.0.1:$pgport/certloom?sslmode=disable" "$bin" migrate
	docker exec "$pg" psql -q -U certloom_owner -d certloom -c "ALTER ROLE certloom_app LOGIN PASSWORD '$app_pw'"

	db="postgres://certloom_app:$app_pw@127.0.0.1:$pgport/certloom?sslmode=disable"
	token=$(CERTLOOM_DATABASE_URL="$db" "$bin" bootstrap --org ansible-test --ttl 12h 2>/dev/null)
	kek=$("$bin" gen-kek)

	# Plain HTTP is fine for a throwaway server; certloomd only allows it on
	# loopback unless told otherwise.
	insecure=
	[ "$listen" = 127.0.0.1 ] || insecure=--insecure-http
	CERTLOOM_DATABASE_URL="$db" CERTLOOM_KEK="$kek" CERTLOOM_LISTEN="$listen:$apiport" \
		CERTLOOM_AGENT_LISTEN="$listen:$agentport" CERTLOOM_AGENT_SERVER_NAMES="$host,localhost,127.0.0.1" \
		CERTLOOM_LOG_LEVEL=warn \
		"$bin" serve $insecure >"$dir/certloomd.log" 2>&1 &
	echo $! >"$dir/certloomd.pid"

	i=0
	until curl -fsS "http://127.0.0.1:$apiport/readyz" >/dev/null 2>&1; do
		i=$((i + 1))
		[ "$i" -lt 60 ] || { cat "$dir/certloomd.log" >&2; exit 1; }
		sleep 1
	done
	umask 077
	mkdir -p "$(dirname "$config")"
	printf 'export CERTLOOM_ENDPOINT=http://%s:%s\nexport CERTLOOM_TOKEN=%s\n' "$host" "$apiport" "$token" >"$dir/env"
	printf -- '---\ncertloom_url: http://%s:%s\ncertloom_token: %s\n' "$host" "$apiport" "$token" >"$config"
	echo "certloomd ready on http://$host:$apiport; source $dir/env"
}

case "${1:-}" in
start) start ;;
stop) stop ;;
*) echo "usage: $0 start|stop" >&2; exit 2 ;;
esac

#!/bin/sh
# Fails if a secret passed to the modules appears in ansible-playbook output
# (normal, check and diff mode, -vvv). Needs CERTLOOM_ENDPOINT and
# CERTLOOM_TOKEN, and the collection on the collections path.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

SCAN_EAB_HMAC=$(printf 'scan-eab-%s' "$(date +%s%N)" | base64 | tr -d '=\n')
SCAN_POOL_HMAC=$(printf 'scan-pool-%s' "$(date +%s%N)" | base64 | tr -d '=\n')
SCAN_DNS_SECRET=scan-dns-$(date +%s%N)
SCAN_TOKEN_FILE=$work/token
export SCAN_EAB_HMAC SCAN_POOL_HMAC SCAN_DNS_SECRET SCAN_TOKEN_FILE

ansible-playbook -vvv --diff "$here/playbook.yml" >"$work/out" 2>&1 || { cat "$work/out"; exit 1; }
ansible-playbook -vvv --diff --check "$here/playbook.yml" >>"$work/out" 2>&1 || { cat "$work/out"; exit 1; }

token=$(cat "$SCAN_TOKEN_FILE")
[ -n "$token" ] || { echo "no enrollment token was created" >&2; exit 1; }
found=0
check() {
	if grep -qF -- "$2" "$work/out"; then
		echo "secret $1 found in playbook output" >&2
		found=1
	fi
}
check eab_hmac "$SCAN_EAB_HMAC"
check pool_hmac "$SCAN_POOL_HMAC"
check dns_secret "$SCAN_DNS_SECRET"
check enrollment_token "$token"
[ "$found" -eq 0 ] && echo "no secrets in playbook output"
exit "$found"

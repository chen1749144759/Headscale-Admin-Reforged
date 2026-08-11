#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_dir/docker/origin-url.sh"

assert_valid() {
  is_http_origin "$1" || {
    echo "expected valid origin: $1" >&2
    exit 1
  }
}

assert_invalid() {
  if is_http_origin "$1"; then
    echo "expected invalid origin: $1" >&2
    exit 1
  fi
}

assert_valid 'http://211.137.214.34:60090'
assert_valid 'https://headscale.example.com'
assert_valid 'http://localhost:8080'
assert_valid 'https://[2001:db8::1]:8443'
assert_valid 'http://headscale.example.com/'
assert_valid 'http://headscale.example.com.:60090'

assert_invalid ''
assert_invalid 'ftp://headscale.example.com'
assert_invalid 'HEADSCALE://headscale.example.com'
assert_invalid 'http://'
assert_invalid 'http://:60090'
assert_invalid 'http://user:password@headscale.example.com'
assert_invalid 'http://headscale.example.com//'
assert_invalid 'http://headscale.example.com/control'
assert_invalid 'http://headscale.example.com?mode=login'
assert_invalid 'http://headscale.example.com#fragment'
assert_invalid 'http://head scale.example.com'
assert_invalid 'http://headscale.example.com:'
assert_invalid 'http://headscale.example.com:abc'
assert_invalid 'http://headscale.example.com:0'
assert_invalid 'http://headscale.example.com:65536'
assert_invalid 'http://2001:db8::1'
assert_invalid 'http://[2001:db8::1]extra'

echo 'manage-account-stack URL validation passed'

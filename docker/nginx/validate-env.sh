#!/bin/sh
set -eu

case "${SCALEFORGE_EXTERNAL_SCHEME:-https}" in
  http|https) ;;
  *)
    echo "SCALEFORGE_EXTERNAL_SCHEME must be http or https" >&2
    exit 1
    ;;
esac

#!/bin/sh

# Return success only for an origin-only HTTP(S) URL. This intentionally uses
# POSIX shell primitives so deployment preflight needs no extra host tools.
is_http_origin() {
  _origin_url=${1-}
  case "$_origin_url" in
    http://*) _origin_authority=${_origin_url#http://} ;;
    https://*) _origin_authority=${_origin_url#https://} ;;
    *) return 1 ;;
  esac

  case "$_origin_authority" in
    */) _origin_authority=${_origin_authority%/} ;;
  esac

  case "$_origin_authority" in
    ''|*'/'*|*'?'*|*'#'*|*'@'*|*[[:space:]]*) return 1 ;;
  esac

  _origin_has_port=0
  _origin_port=
  case "$_origin_authority" in
    \[* )
      _origin_after_open=${_origin_authority#\[}
      case "$_origin_after_open" in
        *\]*) ;;
        *) return 1 ;;
      esac
      _origin_host=${_origin_after_open%%]*}
      _origin_suffix=${_origin_after_open#*]}
      case "$_origin_host" in
        ''|*[!0-9A-Fa-f:.]*|*:::*) return 1 ;;
        *:*) ;;
        *) return 1 ;;
      esac
      case "$_origin_suffix" in
        '') ;;
        :*)
          _origin_has_port=1
          _origin_port=${_origin_suffix#:}
          ;;
        *) return 1 ;;
      esac
      ;;
    *)
      case "$_origin_authority" in
        *:*)
          _origin_host=${_origin_authority%%:*}
          _origin_port=${_origin_authority#*:}
          _origin_has_port=1
          ;;
        *) _origin_host=$_origin_authority ;;
      esac
      case "$_origin_host" in
        *.) _origin_host=${_origin_host%.} ;;
      esac
      case "$_origin_host" in
        ''|*[!A-Za-z0-9.-]*|.*|*.|*..*|*.-*|*-.*|-*|*-) return 1 ;;
      esac
      [ "${#_origin_host}" -le 253 ] || return 1
      ;;
  esac

  if [ "$_origin_has_port" -eq 1 ]; then
    case "$_origin_port" in
      ''|*[!0-9]*) return 1 ;;
    esac
    [ "${#_origin_port}" -le 5 ] || return 1
    [ "$_origin_port" -ge 1 ] 2>/dev/null || return 1
    [ "$_origin_port" -le 65535 ] 2>/dev/null || return 1
  fi

  return 0
}

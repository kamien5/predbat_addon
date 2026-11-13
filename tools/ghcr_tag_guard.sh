#!/usr/bin/env bash
# Fail-closed probe for an immutable GHCR version tag.
#
# Usage:
#   tools/ghcr_tag_guard.sh inspect <image:tag>
#   tools/ghcr_tag_guard.sh classify <exit-code>   # inspect output on stdin
#
# Exit 0 only when the registry confirmed the tag is absent (safe to publish).
# Exit 1 if the tag exists, or if the probe is anything other than a clean
# missing-manifest response (auth, network, 5xx, rate-limit, unrecognized).
set -euo pipefail

AUTH_OR_INFRA_RE='unauthorized|authentication required|access denied|denied:|forbidden|token required|HTTP[/ ]*401|status:? *401|HTTP[/ ]*403|status:? *403|HTTP[/ ]*429|status:? *429|toomanyrequests|rate.?limit|HTTP[/ ]*5[0-9]{2}|status:? *5[0-9]{2}|bad gateway|service unavailable|gateway timeout|connection refused|connection reset|network is unreachable|temporary failure in name resolution|tls handshake|x509|i/o timeout|context deadline exceeded|net/http: TLS|unexpected EOF'

MISSING_RE='manifest unknown|no such manifest|MANIFEST_UNKNOWN|manifest for .+ not found|HTTP[/ ]*404|status:? *404'

classify() {
  local rc="$1"
  local output
  output="$(cat)"
  if [[ "${rc}" -eq 0 ]]; then
    echo "::error::tag already exists; version tags are immutable" >&2
    return 1
  fi
  if printf '%s\n' "${output}" | grep -Eqi "${AUTH_OR_INFRA_RE}"; then
    echo "::error::registry probe failed (auth/network/server); refusing to publish" >&2
    printf '%s\n' "${output}" >&2
    return 1
  fi
  if printf '%s\n' "${output}" | grep -Eqi "${MISSING_RE}"; then
    echo "Tag is absent from the registry; publishing is allowed"
    return 0
  fi
  echo "::error::registry probe failed with an unrecognized error; refusing to publish" >&2
  printf '%s\n' "${output}" >&2
  return 1
}

inspect_tag() {
  local tag="$1"
  local output rc
  set +e
  output="$(docker manifest inspect "${tag}" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "${output}"
  if printf '%s\n' "${output}" | classify "${rc}"; then
    return 0
  fi
  return 1
}

usage() {
  echo "usage: $0 inspect <image:tag>" >&2
  echo "       $0 classify <exit-code>   # inspect output on stdin" >&2
  exit 2
}

case "${1:-}" in
  inspect)
    [[ $# -eq 2 && -n "${2}" ]] || usage
    inspect_tag "$2"
    ;;
  classify)
    [[ $# -eq 2 ]] || usage
    classify "$2"
    ;;
  *)
    usage
    ;;
esac

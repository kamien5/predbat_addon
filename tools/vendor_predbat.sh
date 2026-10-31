#!/usr/bin/env bash
# Vendors Predbat apps/predbat runtime sources into predbat/vendor reproducibly.
set -euo pipefail

TAG="v9.5.0"
EXPECTED_COMMIT="0cfceaaa719b9ce3de1d10185578feffb008908b"
SOURCE_REPO="https://github.com/springfall2008/batpred"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDOR_DIR="${REPO_ROOT}/predbat/vendor"
MANIFEST="${REPO_ROOT}/predbat/MANIFEST.sha256"
VENDOR_TXT="${REPO_ROOT}/predbat/VENDOR.txt"

sha256_cmd() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$@"
  else
    shasum -a 256 "$@"
  fi
}

verify_mode() {
  if [[ ! -f "${MANIFEST}" ]]; then
    echo "error: missing ${MANIFEST}" >&2
    exit 1
  fi
  if [[ ! -d "${VENDOR_DIR}" ]]; then
    echo "error: missing ${VENDOR_DIR}" >&2
    exit 1
  fi

  (
    cd "${VENDOR_DIR}"
    # Verify checksums for every path listed in the manifest.
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum -c ../MANIFEST.sha256
    else
      # macOS shasum -c expects the same "HASH  filename" format.
      shasum -a 256 -c ../MANIFEST.sha256
    fi
  )

  # Exact set equality: vendor files vs manifest filenames.
  local tmp_manifest_files tmp_vendor_files
  tmp_manifest_files="$(mktemp)"
  tmp_vendor_files="$(mktemp)"
  # shellcheck disable=SC2064
  trap "rm -f '${tmp_manifest_files}' '${tmp_vendor_files}'" EXIT

  # Manifest format: "<64 hex>  <filename>" (two spaces).
  awk '{print $2}' "${MANIFEST}" | LC_ALL=C sort >"${tmp_manifest_files}"

  # All regular files under vendor/, paths relative to vendor/.
  (
    cd "${VENDOR_DIR}"
    find . -type f -print | sed 's|^\./||' | LC_ALL=C sort
  ) >"${tmp_vendor_files}"

  if ! cmp -s "${tmp_manifest_files}" "${tmp_vendor_files}"; then
    echo "error: vendor file set does not exactly match MANIFEST.sha256" >&2
    echo "--- manifest only ---" >&2
    comm -23 "${tmp_manifest_files}" "${tmp_vendor_files}" >&2 || true
    echo "--- vendor only ---" >&2
    comm -13 "${tmp_manifest_files}" "${tmp_vendor_files}" >&2 || true
    exit 1
  fi

  echo "verify ok: $(wc -l <"${MANIFEST}" | tr -d ' ') files match MANIFEST.sha256"
}

vendor_mode() {
  local clone="$1"
  if [[ -z "${clone}" ]]; then
    echo "usage: tools/vendor_predbat.sh <path-to-local-batpred-git-clone>" >&2
    echo "       tools/vendor_predbat.sh --verify" >&2
    exit 1
  fi
  if [[ ! -d "${clone}/.git" && ! -f "${clone}/.git" ]]; then
    echo "error: not a git clone: ${clone}" >&2
    exit 1
  fi

  local resolved
  resolved="$(git -C "${clone}" rev-parse "${TAG}^{commit}")"
  if [[ "${resolved}" != "${EXPECTED_COMMIT}" ]]; then
    echo "error: ${TAG} resolves to ${resolved}, expected ${EXPECTED_COMMIT}" >&2
    exit 1
  fi

  local tmp extract_root
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '${tmp}'" EXIT

  # Extract apps/predbat from the pinned commit into a temp tree.
  git -C "${clone}" archive --format=tar "${EXPECTED_COMMIT}" apps/predbat | tar -x -C "${tmp}"
  extract_root="${tmp}/apps/predbat"
  if [[ ! -d "${extract_root}" ]]; then
    echo "error: archive did not contain apps/predbat" >&2
    exit 1
  fi

  # Recreate vendor directory.
  rm -rf "${VENDOR_DIR}"
  mkdir -p "${VENDOR_DIR}"

  # Copy ONLY regular files directly inside apps/predbat (flat into vendor/).
  # tests/ are not runtime code; config/ holds apps.yaml/secrets.yaml templates
  # which must never overwrite user files.
  local f base file_count=0
  for f in "${extract_root}"/*; do
    [[ -e "${f}" ]] || continue
    if [[ -f "${f}" ]]; then
      base="$(basename "${f}")"
      cp "${f}" "${VENDOR_DIR}/${base}"
      file_count=$((file_count + 1))
    fi
  done

  if [[ "${file_count}" -eq 0 ]]; then
    echo "error: no regular files found in apps/predbat" >&2
    exit 1
  fi

  # MANIFEST.sha256: plain sha256sum format, LC_ALL=C sorted, relative to vendor/.
  (
    cd "${VENDOR_DIR}"
    # shellcheck disable=SC2035
    LC_ALL=C sha256_cmd * | LC_ALL=C sort -k2
  ) >"${MANIFEST}"

  # Reproducible VENDOR.txt (no timestamps).
  {
    echo "source: ${SOURCE_REPO}"
    echo "tag: ${TAG}"
    echo "commit: ${EXPECTED_COMMIT}"
    echo "file_count: ${file_count}"
    echo "excluded_subdirectories: tests/ config/"
    echo "produced_by: tools/vendor_predbat.sh <clone>"
    echo "archive_command: git -C <clone> archive --format=tar ${EXPECTED_COMMIT} apps/predbat | tar -x -C <tmp>"
    echo "verify: cd predbat/vendor && sha256sum -c ../MANIFEST.sha256"
  } >"${VENDOR_TXT}"

  echo "vendored ${file_count} files from ${TAG} (${EXPECTED_COMMIT}) into predbat/vendor/"
}

main() {
  if [[ "${1:-}" == "--verify" ]]; then
    verify_mode
  else
    vendor_mode "${1:-}"
  fi
}

main "$@"

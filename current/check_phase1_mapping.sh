#!/usr/bin/env bash
set -euo pipefail

SAMPLE_FILE="current/songs_last_20min_sample.json"
MAPPING_FILE="current/radio_bob_mapping.jq"

if [[ ! -f "${SAMPLE_FILE}" ]]; then
  echo "missing sample file: ${SAMPLE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${MAPPING_FILE}" ]]; then
  echo "missing mapping file: ${MAPPING_FILE}" >&2
  exit 1
fi

echo "Sample found:" "$(jq -r '.result.found' "${SAMPLE_FILE}")"
echo "Mapped preview (first 3):"
jq -c -f "${MAPPING_FILE}" "${SAMPLE_FILE}" | head -n 3

echo "Mapped count:" "$(jq -f "${MAPPING_FILE}" "${SAMPLE_FILE}" | jq -s 'length')"

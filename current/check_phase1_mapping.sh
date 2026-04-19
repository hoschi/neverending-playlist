#!/usr/bin/env bash
set -euo pipefail

SAMPLE_FILE="current/songs_last_20min_sample.json"
MAPPING_FILE="current/radio_bob_mapping.jq"
SOURCE_URL="${SOURCE_URL:-https://iris-bob.loverad.io/search.json?station=110}"
SOURCE_DOMAIN="${SOURCE_URL#*://}"
SOURCE_DOMAIN="${SOURCE_DOMAIN%%/*}"

if [[ ! -f "${SAMPLE_FILE}" ]]; then
  echo "missing sample file: ${SAMPLE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${MAPPING_FILE}" ]]; then
  echo "missing mapping file: ${MAPPING_FILE}" >&2
  exit 1
fi

echo "Sample found:" "$(jq -r '.result.found' "${SAMPLE_FILE}")"
echo "Derived source:" "${SOURCE_DOMAIN}"
echo "Mapped preview (first 3):"
jq -c --arg source "${SOURCE_DOMAIN}" -f "${MAPPING_FILE}" "${SAMPLE_FILE}" | head -n 3

echo "Mapped count:" "$(jq --arg source "${SOURCE_DOMAIN}" -f "${MAPPING_FILE}" "${SAMPLE_FILE}" | jq -s 'length')"

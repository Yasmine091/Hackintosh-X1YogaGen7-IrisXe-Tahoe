#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s DESTINATION_DIR\n' "$0" >&2
  exit 2
fi

yoga_output_dir=$1
yoga_asset_name='AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-738d4c6.zip'
yoga_asset_url="https://github.com/laobamac/itlwm/releases/download/v2.4.0-alpha/${yoga_asset_name}"
yoga_expected_sha256='25680aa39ddd79b205141875b261bdcc28bea150d13f27787b3c215555daa00f'

mkdir -p -- "$yoga_output_dir"
yoga_output_file="${yoga_output_dir%/}/${yoga_asset_name}"
yoga_partial_file="${yoga_output_file}.part.$$"

if [[ -e "$yoga_output_file" || -e "$yoga_partial_file" ]]; then
  printf 'Refusing to overwrite existing file: %s\n' "$yoga_output_file" >&2
  exit 1
fi

trap 'rm -f -- "$yoga_partial_file"' EXIT
curl --fail --location --silent --show-error \
  --output "$yoga_partial_file" "$yoga_asset_url"
printf '%s  %s\n' "$yoga_expected_sha256" "$yoga_partial_file" | sha256sum --check
if [[ -e "$yoga_output_file" ]]; then
  printf 'Refusing to overwrite existing file: %s\n' "$yoga_output_file" >&2
  exit 1
fi
mv -- "$yoga_partial_file" "$yoga_output_file"
trap - EXIT
printf 'Verified download: %s\n' "$yoga_output_file"

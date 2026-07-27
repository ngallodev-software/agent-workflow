#!/usr/bin/env bash
set -euo pipefail

pack_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "$pack_root/../.." && pwd)"
out_dir="${1:-$repo_root/dist}"
pack_id="delegation-communication-reliability"
mkdir -p "$out_dir"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

tar_name="$out_dir/${pack_id}.tar.zst"
manifest="$tmp_dir/MANIFEST.sha256"
(
  cd "$pack_root"
  find . -type f ! -name '*.sha256' -print0 | sort -z | xargs -0 sha256sum
) > "$manifest"
cp "$manifest" "$pack_root/MANIFEST.sha256"
tar -C "$(dirname "$pack_root")" -cf - "$(basename "$pack_root")" | zstd -q -f -o "$tar_name"
sha256sum "$tar_name" > "$tar_name.sha256"
rm -f "$pack_root/MANIFEST.sha256"
printf '%s\n' "$tar_name"

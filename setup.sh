#!/usr/bin/env bash
# Build hashcat from source. Use this on systems where no prebuilt binary
# is available (e.g. ARM64 / aarch64 — hashcat ships x86_64 binaries only).
#
# Requires: build-essential, curl, an NVIDIA CUDA toolkit if you want GPU
# acceleration (hashcat detects CUDA at runtime; no link-time dependency).
#
# Override VERSION or HASHCAT_PREFIX via env vars if you want a different
# release or install location.
set -euo pipefail

VERSION="${HASHCAT_VERSION:-7.1.2}"
PREFIX="${HASHCAT_PREFIX:-$HOME/hashcat-${VERSION}}"
SRC_URL="https://hashcat.net/files/hashcat-${VERSION}.tar.gz"

echo ">> Installing build dependencies (sudo required)"
sudo apt-get update
sudo apt-get install -y build-essential curl

if [ -d "$PREFIX" ]; then
  echo ">> $PREFIX already exists, skipping download/extract"
else
  TMPDIR=$(mktemp -d)
  trap 'rm -rf "$TMPDIR"' EXIT
  echo ">> Downloading hashcat ${VERSION}"
  curl -fL "$SRC_URL" -o "$TMPDIR/hashcat.tar.gz"
  echo ">> Extracting to $(dirname "$PREFIX")"
  mkdir -p "$(dirname "$PREFIX")"
  tar -xzf "$TMPDIR/hashcat.tar.gz" -C "$(dirname "$PREFIX")"
fi

echo ">> Building (this takes a few minutes)"
make -C "$PREFIX" -j"$(nproc)"

if [ -x "$PREFIX/hashcat" ]; then
  HASHCAT_BIN_PATH="$PREFIX/hashcat"
elif [ -x "$PREFIX/hashcat.bin" ]; then
  HASHCAT_BIN_PATH="$PREFIX/hashcat.bin"
else
  echo "ERROR: hashcat binary not found in $PREFIX after build" >&2
  exit 1
fi

echo ">> Smoke test"
"$HASHCAT_BIN_PATH" --version

cat <<EOF

Done. Point the runner at this binary by exporting HASHCAT_BIN:

  export HASHCAT_BIN=$HASHCAT_BIN_PATH

Then sync the Python project and start the sweep:

  uv sync
  uv run hash-cracking
EOF

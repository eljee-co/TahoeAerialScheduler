#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

VERSION="${1:-}"

if [[ -z "${VERSION}" ]]; then
  echo "Usage: ./scripts/package-release.sh v0.1.0" >&2
  exit 1
fi

STAGING_DIR="${REPO_ROOT}/dist/TahoeAerialScheduler-${VERSION}"
ARCHIVE_PATH="${REPO_ROOT}/dist/TahoeAerialScheduler-${VERSION}.zip"

rm -rf "${STAGING_DIR}" "${ARCHIVE_PATH}"
mkdir -p "${REPO_ROOT}/dist"

rsync -a \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${REPO_ROOT}/" "${STAGING_DIR}/"

(cd "${REPO_ROOT}/dist" && zip -rq "TahoeAerialScheduler-${VERSION}.zip" "TahoeAerialScheduler-${VERSION}")

echo "Created release archive:"
echo "  ${ARCHIVE_PATH}"


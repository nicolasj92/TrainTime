#!/usr/bin/env bash
# Make a new release: ./deploy/release.sh 1.2.0
# Writes VERSION, commits, tags v1.2.0 and pushes; GitHub Actions then publishes the release
# (.github/workflows/release.yml) and every Pi's System page offers it as an update.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:?usage: deploy/release.sh X.Y.Z}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must look like 1.2.0"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "commit your changes first"; exit 1; }
[[ "$(git branch --show-current)" == master ]] || { echo "release from master"; exit 1; }
git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null && { echo "v$VERSION exists already"; exit 1; }
echo "$VERSION" > VERSION
git commit -qm "Release v$VERSION" VERSION
git tag -a "v$VERSION" -m "v$VERSION"
git push -q origin master "v$VERSION"
echo "Pushed v$VERSION. Release: https://github.com/nicolasj92/TrainTime/releases/tag/v$VERSION"

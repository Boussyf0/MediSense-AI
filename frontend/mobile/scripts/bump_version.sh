#!/usr/bin/env bash
# Bump the Flutter app version in pubspec.yaml.
#
# Play Store requires a STRICTLY INCREASING versionCode (the "+N" build number)
# for every upload. versionName (the "X.Y.Z" part) is what users see.
#
# Usage:
#   ./scripts/bump_version.sh build      # 1.0.0+1  -> 1.0.0+2   (default; most releases)
#   ./scripts/bump_version.sh patch      # 1.0.0+1  -> 1.0.1+2
#   ./scripts/bump_version.sh minor      # 1.0.3+5  -> 1.1.0+6
#   ./scripts/bump_version.sh major      # 1.4.2+9  -> 2.0.0+10
#   ./scripts/bump_version.sh            # same as "build"
#
# Always bumps the build number too, so the upload is never rejected.
set -euo pipefail

cd "$(dirname "$0")/.."   # -> frontend/mobile
PUBSPEC="pubspec.yaml"

part="${1:-build}"

current="$(grep -E '^version:' "$PUBSPEC" | head -1 | sed -E 's/^version:[[:space:]]*//')"
name="${current%%+*}"      # 1.0.0
code="${current##*+}"      # 1
IFS='.' read -r major minor patch <<< "$name"

case "$part" in
  major) major=$((major+1)); minor=0; patch=0 ;;
  minor) minor=$((minor+1)); patch=0 ;;
  patch) patch=$((patch+1)) ;;
  build) ;;  # name unchanged, only build number bumps below
  *) echo "Unknown part: '$part' (use: build | patch | minor | major)" >&2; exit 1 ;;
esac

code=$((code+1))
new="${major}.${minor}.${patch}+${code}"

# Portable in-place edit (macOS/BSD + GNU sed).
sed -i.bak -E "s/^version:.*/version: ${new}/" "$PUBSPEC"
rm -f "${PUBSPEC}.bak"

echo "Version: ${current}  ->  ${new}"
echo "  versionName = ${major}.${minor}.${patch}"
echo "  versionCode = ${code}"

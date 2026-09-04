#!/usr/bin/env bash
# AutoTask 发版 promote：staging/<stagingId> → releases/<version>，原子切换 stable 软链。
# 放在服务器 /data/smc-release/autotask/promote-autotask-release.sh
# 用法: promote-autotask-release.sh <version> <stagingId>
set -euo pipefail

VERSION="${1:?usage: promote-autotask-release.sh <version> <stagingId>}"
STAGING_ID="${2:?usage: promote-autotask-release.sh <version> <stagingId>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

STAGING="$ROOT/staging/$STAGING_ID"
RELEASE="$ROOT/releases/$VERSION"

[ -d "$STAGING" ] || { echo "staging 不存在: $STAGING" >&2; exit 1; }
[ ! -e "$RELEASE" ] || { echo "版本目录已存在（不可变）: $RELEASE" >&2; exit 1; }

# 必备产物
for f in "AutoTask-Studio-$VERSION-setup.exe" "AutoTask-Studio-$VERSION-setup.exe.blockmap" "latest.yml" "SHA256SUMS.txt"; do
  [ -f "$STAGING/$f" ] || { echo "缺少产物: $f" >&2; exit 1; }
done

# 校验 exe 的 sha256
( cd "$STAGING" && sha256sum -c SHA256SUMS.txt )

mv "$STAGING" "$RELEASE"
ln -sfn "$RELEASE" "$ROOT/stable.new"
mv -Tf "$ROOT/stable.new" "$ROOT/stable"

echo "promoted: autotask $VERSION -> stable"

#!/usr/bin/env bash
# AutoTask 回滚：把 stable 软链指回旧版本。不影响已经更新完的客户端。
# 放在服务器 /data/smc-release/autotask/rollback-autotask-stable.sh
# 用法: rollback-autotask-stable.sh <version>
set -euo pipefail

VERSION="${1:?usage: rollback-autotask-stable.sh <version>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE="$ROOT/releases/$VERSION"

[ -d "$RELEASE" ] || { echo "版本目录不存在: $RELEASE" >&2; exit 1; }

ln -sfn "$RELEASE" "$ROOT/stable.new"
mv -Tf "$ROOT/stable.new" "$ROOT/stable"

echo "rolled back: autotask stable -> $VERSION"

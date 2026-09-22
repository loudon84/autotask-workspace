#!/usr/bin/env sh
# AutoTask 发版 promote：staging/<stagingId> → releases/<version>，原子切换 stable。
# 流程与 Work 的 promote-work-release.sh 保持一致（同样的错误码、相对软链、
# mkdir -p releases）。唯一差异是发布门禁：Work 验 Authenticode 签名 +
# release-manifest.json signed:true；AutoTask 不验签名，改为校验产物齐全、
# SHA256SUMS、latest.yml 的 version/path/sha512。
# 放在服务器 /data/smc-release/autotask/promote-autotask-release.sh
# 用法: promote-autotask-release.sh <version> <staging-id>
set -eu

VERSION="${1:-}"
STAGING_ID="${2:-}"
RELEASE_ROOT="${RELEASE_ROOT:-/data/smc-release/autotask}"

if [ -z "${VERSION}" ] || [ -z "${STAGING_ID}" ]; then
  echo "Usage: promote-autotask-release.sh <version> <staging-id>" >&2
  exit 1
fi

case "${VERSION}" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *)
    echo "PROMOTION_FAILED: INVALID_VERSION" >&2
    exit 1
    ;;
esac

STAGING_DIR="${RELEASE_ROOT}/staging/${STAGING_ID}"
RELEASES_DIR="${RELEASE_ROOT}/releases"
TARGET_DIR="${RELEASES_DIR}/${VERSION}"
INSTALLER="AutoTask-Studio-${VERSION}-setup.exe"

if [ ! -d "${STAGING_DIR}" ]; then
  echo "PROMOTION_FAILED: STAGING_NOT_FOUND" >&2
  exit 1
fi

# --- AutoTask 完整性门禁（替代 Work 的签名门禁） ---
for f in "${INSTALLER}" "${INSTALLER}.blockmap" "latest.yml" "SHA256SUMS.txt" "release-manifest.json"; do
  if [ ! -f "${STAGING_DIR}/${f}" ]; then
    echo "PROMOTION_FAILED: MISSING_ARTIFACT ${f}" >&2
    exit 1
  fi
done

# 可追溯门禁：manifest 版本必须匹配，且带有效 gitCommit（对齐 Work 的 git 身份要求）
MANIFEST_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${STAGING_DIR}/release-manifest.json" | head -n 1)"
if [ "${MANIFEST_VERSION}" != "${VERSION}" ]; then
  echo "PROMOTION_FAILED: MANIFEST_VERSION_MISMATCH" >&2
  exit 1
fi
if ! grep -q '"gitCommit"[[:space:]]*:[[:space:]]*"[0-9a-f]\{7,\}"' "${STAGING_DIR}/release-manifest.json"; then
  echo "PROMOTION_FAILED: MANIFEST_NO_GIT_COMMIT" >&2
  exit 1
fi

if ! ( cd "${STAGING_DIR}" && sha256sum -c SHA256SUMS.txt ); then
  echo "PROMOTION_FAILED: SHA256_MISMATCH" >&2
  exit 1
fi

LATEST_VERSION="$(sed -n 's/^version:[[:space:]]*//p' "${STAGING_DIR}/latest.yml" | head -n 1 | tr -d "\"'")"
if [ "${LATEST_VERSION}" != "${VERSION}" ]; then
  echo "PROMOTION_FAILED: LATEST_VERSION_MISMATCH" >&2
  exit 1
fi

LATEST_PATH="$(sed -n 's/^path:[[:space:]]*//p' "${STAGING_DIR}/latest.yml" | head -n 1 | tr -d "\"'")"
if [ "${LATEST_PATH##*/}" != "${INSTALLER}" ]; then
  echo "PROMOTION_FAILED: LATEST_PATH_MISMATCH" >&2
  exit 1
fi

LATEST_SHA512="$(sed -n 's/^sha512:[[:space:]]*//p' "${STAGING_DIR}/latest.yml" | head -n 1 | tr -d "\"' ")"
ACTUAL_SHA512="$(openssl dgst -sha512 -binary "${STAGING_DIR}/${INSTALLER}" | openssl base64 -A)"
if [ -z "${LATEST_SHA512}" ] || [ "${LATEST_SHA512}" != "${ACTUAL_SHA512}" ]; then
  echo "PROMOTION_FAILED: LATEST_SHA512_MISMATCH" >&2
  exit 1
fi
# --- 门禁结束 ---

if [ -e "${TARGET_DIR}" ]; then
  echo "PROMOTION_FAILED: RELEASE_ALREADY_EXISTS" >&2
  exit 1
fi

mkdir -p "${RELEASES_DIR}"
mv "${STAGING_DIR}" "${TARGET_DIR}"
ln -s "releases/${VERSION}" "${RELEASE_ROOT}/stable.new"
mv -Tf "${RELEASE_ROOT}/stable.new" "${RELEASE_ROOT}/stable"

echo "promoted: autotask ${VERSION} -> stable"

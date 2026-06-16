#!/usr/bin/env bash
# 安装 Git hooks 到 .git/hooks/
# 每次 clone 仓库后运行一次即可。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOKS_SRC="$REPO_ROOT/scripts/git-hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

echo "==> 安装 Git hooks..."

for hook in pre-commit; do
  src="$HOOKS_SRC/$hook"
  dst="$HOOKS_DST/$hook"
  if [ -f "$src" ]; then
    cp "$src" "$dst"
    chmod +x "$dst"
    echo "    $hook 已安装"
  fi
done

echo "==> 完成。后续每次 git commit 都会自动检查 API Key。"

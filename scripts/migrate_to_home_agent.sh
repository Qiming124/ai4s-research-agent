#!/usr/bin/env bash
# 将项目从 /home/silverwolf/agent 迁移到 Cursor 工作区 /home/agent
# 用法（root 终端）：bash /home/silverwolf/agent/scripts/migrate_to_home_agent.sh

set -euo pipefail

SRC="/home/silverwolf/agent"
DEST="/home/agent"
OWNER="${SUDO_USER:-silverwolf}"

echo "==> 源目录: $SRC"
echo "==> 目标目录: $DEST"
echo "==> 目标所有者: $OWNER"

# 清理工作区中的旧占位目录（若存在）
for dir in app common config doc; do
  if [[ -d "$DEST/$dir" ]]; then
    echo "==> 删除旧目录 $DEST/$dir"
    rm -rf "$DEST/$dir"
  fi
done

# 同步源码（排除虚拟环境、缓存、egg-info；保留 .git）
echo "==> 同步文件..."
rsync -av \
  --exclude='.venv' \
  --exclude='.pytest_cache' \
  --exclude='*.egg-info' \
  --exclude='.env' \
  "$SRC/" "$DEST/"

# 若存在用户自定义 .env，可选复制（取消下一行注释）
# [[ -f "$SRC/.env" ]] && cp "$SRC/.env" "$DEST/.env"

# 设置目录所有者（便于 silverwolf 用户日常开发）
if id "$OWNER" &>/dev/null; then
  echo "==> chown -R $OWNER:$OWNER $DEST"
  chown -R "$OWNER:$OWNER" "$DEST"
fi

echo ""
echo "==> 迁移完成！后续步骤："
echo "    cd $DEST"
echo "    cp .env.example .env   # 填入 DEEPSEEK_API_KEY"
echo "    python3 -m pip install -e ."
echo "    uvicorn server.main:app --reload --host 0.0.0.0 --port 8000"

#!/bin/sh
# Seed theory / experiment configs into persistent volume on first start.
set -eu
SEED_THEORY=/opt/seed/theory
SEED_EXPERIMENTS=/opt/seed/experiments/configs

mkdir -p /repo/data/mcp_files /repo/data/chroma /repo/data/theory \
  /repo/data/experiments/logs /repo/data/experiments/notebooks \
  /repo/data/experiments/configs /repo/data/projects /repo/log

if [ -d "$SEED_THEORY" ]; then
  # Copy missing seed files only (do not overwrite user edits)
  cp -an "$SEED_THEORY/." /repo/data/theory/ 2>/dev/null || \
    cp -a "$SEED_THEORY/." /repo/data/theory/
fi
if [ -d "$SEED_EXPERIMENTS" ]; then
  cp -an "$SEED_EXPERIMENTS/." /repo/data/experiments/configs/ 2>/dev/null || \
    cp -a "$SEED_EXPERIMENTS/." /repo/data/experiments/configs/
fi

exec "$@"

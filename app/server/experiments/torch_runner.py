# PyTorch 神经网络实验：宽度缩放、Hessian 最小特征值、SGD 轨迹。

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import get_settings


def run_torch_experiment(config: dict[str, Any]) -> dict[str, Any]:
    """执行小型 MLP 实验（若 PyTorch 不可用则返回 skipped）。"""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return {
            "status": "skipped",
            "reason": "PyTorch 未安装",
            "details": {},
        }

    run_id = str(uuid.uuid4())[:8]
    settings = get_settings()
    network = config.get("network", [2, 16, 1])
    width = int(config.get("width", network[1] if len(network) > 1 else 16))
    seeds = config.get("seeds", [0])
    seed = int(seeds[0]) if seeds else 0
    torch.manual_seed(seed)

    in_dim = int(network[0]) if network else 2
    out_dim = int(network[-1]) if network else 1

    class TinyMLP(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_dim, width),
                nn.ReLU(),
                nn.Linear(width, out_dim),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

    model = TinyMLP()
    x = torch.randn(32, in_dim)
    y = torch.randn(32, out_dim)
    loss_fn = nn.MSELoss()

    def compute_loss() -> torch.Tensor:
        pred = model(x)
        return loss_fn(pred, y)

    loss = compute_loss()
    params = [p for p in model.parameters() if p.requires_grad]
    grads = torch.autograd.grad(loss, params, create_graph=True)
    grad_vec = torch.cat([g.reshape(-1) for g in grads])

    hessian_rows = []
    for i in range(min(grad_vec.numel(), 64)):
        row = torch.autograd.grad(grad_vec[i], params, retain_graph=True)
        hessian_rows.append(torch.cat([r.reshape(-1) for r in row]))
    if hessian_rows:
        hessian = torch.stack(hessian_rows)
        eigvals = torch.linalg.eigvalsh(hessian @ hessian.T)
        min_eig = float(eigvals.min().item())
        max_eig = float(eigvals.max().item())
    else:
        min_eig = 0.0
        max_eig = 0.0

    trajectory: list[float] = []
    opt = torch.optim.SGD(model.parameters(), lr=0.01)
    for _ in range(10):
        opt.zero_grad()
        l = compute_loss()
        l.backward()
        opt.step()
        trajectory.append(float(l.item()))

    summary = {
        "network": network,
        "width": width,
        "seed": seed,
        "loss_initial": float(loss.item()),
        "hessian_min_eig": min_eig,
        "hessian_max_eig": max_eig,
        "sgd_trajectory": trajectory,
        "classification_hint": (
            "local_minimum" if min_eig > 1e-6 else "saddle_or_indefinite"
        ),
    }

    record = {
        "run_id": run_id,
        "name": config.get("name", "torch_mlp_experiment"),
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }

    logs_dir = Path(settings.experiments_path) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"torch_{run_id}.json"
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["log_path"] = str(log_path)
    return record

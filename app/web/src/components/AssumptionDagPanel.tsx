import { useMemo, useState } from "react";
import type { DagEdge, DagNode } from "../hooks/useAssumptionDag";

interface AssumptionDagPanelProps {
  nodes: DagNode[];
  edges: DagEdge[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onImpact: (id: string) => Promise<unknown>;
}

interface ImpactResult {
  assumption: string;
  affected: { id: string | number; kind?: string; title: string; status?: string }[];
  error?: string;
}

const KIND_LABEL: Record<string, string> = {
  theorem: "定理",
  hypothesis: "假设条目",
  conclusion: "结论",
  assumption: "假设",
  note: "笔记",
};

function kindLabel(kind?: string): string {
  if (!kind) return "条目";
  return KIND_LABEL[kind] ?? kind;
}

function impactQueryId(node: DagNode): string | null {
  if (node.kind === "assumption") {
    return node.title || String(node.id).replace(/^assumption-/i, "");
  }
  return null;
}

function parseImpact(data: unknown, fallbackId: string): ImpactResult {
  if (!data || typeof data !== "object") {
    return { assumption: fallbackId, affected: [], error: "无法解析影响结果" };
  }
  const raw = data as Record<string, unknown>;
  const assumption = String(raw.assumption ?? fallbackId);
  const list = Array.isArray(raw.affected) ? raw.affected : [];
  const affected = list
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      id: (item.id as string | number) ?? "",
      kind: item.kind != null ? String(item.kind) : undefined,
      title: String(item.title ?? item.id ?? "未命名"),
      status: item.status != null ? String(item.status) : undefined,
    }));
  return { assumption, affected };
}

/** 按假设分组：A1 → 依赖它的定理列表 */
function groupByAssumption(
  assumptions: DagNode[],
  theorems: DagNode[],
  requiresEdges: DagEdge[],
): { assumption: DagNode; dependents: DagNode[] }[] {
  const theoremById = new Map(theorems.map((t) => [String(t.id), t]));
  return assumptions.map((a) => {
    const aid = String(a.id);
    const fromEdges = requiresEdges
      .filter((e) => String(e.to_id) === aid)
      .map((e) => theoremById.get(String(e.from_id)))
      .filter((t): t is DagNode => !!t);

    // 也用节点上的 assumptions 字段兜底（边缺失时）
    const fromMeta = theorems.filter((t) =>
      (t.assumptions ?? []).some(
        (x) => x.toUpperCase() === a.title.toUpperCase() || `assumption-${x}` === aid,
      ),
    );

    const seen = new Set<string>();
    const dependents: DagNode[] = [];
    for (const t of [...fromEdges, ...fromMeta]) {
      const key = String(t.id);
      if (seen.has(key)) continue;
      seen.add(key);
      dependents.push(t);
    }
    return { assumption: a, dependents };
  });
}

export function AssumptionDagPanel({
  nodes,
  edges,
  loading,
  error,
  onRefresh,
  onImpact,
}: AssumptionDagPanelProps) {
  const [selectedAid, setSelectedAid] = useState<string | null>(null);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);

  const assumptions = useMemo(
    () => nodes.filter((n) => n.kind === "assumption"),
    [nodes],
  );
  const theorems = useMemo(
    () => nodes.filter((n) => n.kind !== "assumption"),
    [nodes],
  );
  const requiresEdges = useMemo(
    () => edges.filter((e) => e.relation === "requires"),
    [edges],
  );
  const groups = useMemo(
    () => groupByAssumption(assumptions, theorems, requiresEdges),
    [assumptions, theorems, requiresEdges],
  );
  const linkedCount = groups.filter((g) => g.dependents.length > 0).length;

  const handleImpact = async (node: DagNode) => {
    const aid = impactQueryId(node);
    if (!aid) return;
    setSelectedAid(aid);
    setImpactLoading(true);
    setImpact(null);
    try {
      const data = await onImpact(aid);
      setImpact(parseImpact(data, aid));
    } catch (err) {
      setImpact({
        assumption: aid,
        affected: [],
        error: err instanceof Error ? err.message : "查询失败",
      });
    } finally {
      setImpactLoading(false);
    }
  };

  return (
    <div className="assumption-dag-panel">
      <div className="panel-header">
        <h4>假设依赖图</h4>
        <button type="button" className="btn-small" onClick={onRefresh} disabled={loading}>
          刷新
        </button>
      </div>
      {error && <p className="panel-error">{error}</p>}
      {loading && <p className="panel-muted">加载中…</p>}

      {!loading && (
        <p className="dag-summary">
          共 {theorems.length} 条定理/引理，其中 {linkedCount} 个假设有明确依赖。
          点击假设可查看「若该假设失效」会波及哪些结论。
        </p>
      )}

      <div className="dag-assumption-chips" role="group" aria-label="选择假设">
        {assumptions.map((n) => {
          const aid = n.title;
          const count =
            groups.find((g) => g.assumption.id === n.id)?.dependents.length ?? 0;
          const active = selectedAid === aid;
          return (
            <button
              key={String(n.id)}
              type="button"
              className={active ? "dag-chip active" : "dag-chip"}
              onClick={() => void handleImpact(n)}
              disabled={impactLoading}
              title={count > 0 ? `${count} 条结论依赖此假设` : "暂无依赖条目"}
            >
              <span className="dag-chip-id">{aid}</span>
              <span className="dag-chip-count">{count}</span>
            </button>
          );
        })}
      </div>

      {(impactLoading || impact) && (
        <section className="dag-impact-card" aria-live="polite">
          {impactLoading && <p className="panel-muted">正在分析失效影响…</p>}
          {!impactLoading && impact && (
            <>
              <h5 className="dag-impact-title">
                若假设 <strong>{impact.assumption}</strong> 失效
              </h5>
              {impact.error && <p className="panel-error">{impact.error}</p>}
              {!impact.error && impact.affected.length === 0 && (
                <p className="panel-muted">当前会话中没有依赖该假设的定理或引理。</p>
              )}
              {!impact.error && impact.affected.length > 0 && (
                <>
                  <p className="dag-impact-lead">
                    可能受到影响的结论共 <strong>{impact.affected.length}</strong> 条：
                  </p>
                  <ol className="dag-impact-list">
                    {impact.affected.map((item) => (
                      <li key={String(item.id)}>
                        <span className="dag-kind">{kindLabel(item.kind)}</span>
                        <span className="dag-impact-item-title">{item.title}</span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </>
          )}
        </section>
      )}

      <section className="dag-groups">
        <h5 className="dag-section-title">按假设查看依赖</h5>
        {groups.map(({ assumption, dependents }) => (
          <article key={String(assumption.id)} className="dag-group-card">
            <header className="dag-group-head">
              <button
                type="button"
                className="dag-group-aid"
                onClick={() => void handleImpact(assumption)}
              >
                {assumption.title}
              </button>
              <span className="dag-group-meta">
                {dependents.length === 0
                  ? "暂无依赖"
                  : `${dependents.length} 条依赖`}
              </span>
            </header>
            {dependents.length > 0 ? (
              <ul className="dag-dependent-list">
                {dependents.map((t) => (
                  <li key={String(t.id)}>
                    <span className="dag-kind">{kindLabel(t.kind)}</span>
                    <span>{t.title}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dag-group-empty">尚无定理/引理标明依赖此假设</p>
            )}
          </article>
        ))}
      </section>

      {!loading && theorems.length === 0 && (
        <p className="panel-muted">
          当前会话暂无定理条目；对话产出引理/定理并标注依赖假设后，会出现在这里。
        </p>
      )}
    </div>
  );
}

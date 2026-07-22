import { useCallback, useEffect, useState } from "react";
import { useArtifacts, type ArtifactSummary } from "../hooks/useArtifacts";

interface ArtifactsPanelProps {
  projectId: string;
  sessionId?: string;
  types: string[];
  title: string;
  emptyHint?: string;
  /** experiment-plans：按时间线展示历史实验计划 + 读数建议 */
  mode?: "default" | "experiment-plans";
}

const TYPE_LABEL: Record<string, string> = {
  ExperimentPlan: "实验计划",
  NextStepMemo: "读数建议",
  DataPacket: "数据包",
  DerivationTrace: "推导轨迹",
};

const STATUS_LABEL: Record<string, string> = {
  planned: "待做",
  active: "进行中",
  done: "已完成",
  superseded: "已取代",
};

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToLines(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value.map(String).join("\n");
}

function formatWhen(iso?: string): string {
  if (!iso) return "";
  return iso.slice(0, 19).replace("T", " ");
}

export function ArtifactsPanel({
  projectId,
  sessionId,
  types,
  title,
  emptyHint,
  mode = "default",
}: ArtifactsPanelProps) {
  const { artifacts, loading, error, refresh, create, update, remove } = useArtifacts(
    projectId,
    types,
    {
      limit: mode === "experiment-plans" ? 80 : 30,
    },
  );
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [creatingType, setCreatingType] = useState<"ExperimentPlan" | "NextStepMemo" | null>(
    null,
  );
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadDetail = useCallback(
    async (id: string) => {
      if (expandedId === id) {
        setExpandedId(null);
        setDetail(null);
        setEditing(false);
        return;
      }
      setExpandedId(id);
      setEditing(false);
      setDetailLoading(true);
      setDetail(null);
      try {
        const params = new URLSearchParams({ project_id: projectId || "default" });
        const res = await fetch(`/v1/artifacts/${encodeURIComponent(id)}?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { data: Record<string, unknown> };
        setDetail(data.data || null);
      } catch {
        setDetail({ _error: "加载详情失败" });
      } finally {
        setDetailLoading(false);
      }
    },
    [expandedId, projectId],
  );

  useEffect(() => {
    setExpandedId(null);
    setDetail(null);
    setEditing(false);
    setCreatingType(null);
  }, [projectId, types.join(",")]);

  const planCount = artifacts.filter((a) => a.type === "ExperimentPlan").length;
  const memoCount = artifacts.filter((a) => a.type === "NextStepMemo").length;
  const editableMode = mode === "experiment-plans";

  function startCreate(type: "ExperimentPlan" | "NextStepMemo") {
    setCreatingType(type);
    setFormError(null);
    if (type === "ExperimentPlan") {
      setForm({
        title: "",
        objectives: "",
        variables: "",
        controls: "",
        success_criteria: "",
        record_fields: "",
        notes: "",
        status: "planned",
        claim_or_theorem_ref: "",
        revision_note: "",
        hyperparams: "{}",
      });
    } else {
      setForm({
        title: "",
        verdict: "inconclusive",
        missing_data: "",
        next_experiments: "",
        notes: "",
        data_packet_id: "",
        claim_ref: "",
      });
    }
  }

  function startEdit(type: string, data: Record<string, unknown>) {
    setEditing(true);
    setFormError(null);
    if (type === "ExperimentPlan") {
      setForm({
        title: String(data.title || ""),
        objectives: String(data.objectives || ""),
        variables: listToLines(data.variables),
        controls: listToLines(data.controls),
        success_criteria: listToLines(data.success_criteria),
        record_fields: listToLines(data.record_fields),
        notes: String(data.notes || ""),
        status: String(data.status || "planned"),
        claim_or_theorem_ref: String(data.claim_or_theorem_ref || ""),
        revision_note: String(data.revision_note || ""),
        hyperparams: JSON.stringify(data.hyperparams || {}, null, 2),
      });
    } else {
      setForm({
        title: String(data.title || ""),
        verdict: String(data.verdict || "inconclusive"),
        missing_data: listToLines(data.missing_data),
        next_experiments: listToLines(data.next_experiments),
        notes: String(data.notes || ""),
        data_packet_id: String(data.data_packet_id || ""),
        claim_ref: String(data.claim_ref || ""),
      });
    }
  }

  function buildPayload(type: "ExperimentPlan" | "NextStepMemo"): Record<string, unknown> {
    if (type === "ExperimentPlan") {
      let hyperparams: Record<string, unknown> = {};
      try {
        hyperparams = JSON.parse(form.hyperparams || "{}") as Record<string, unknown>;
      } catch {
        throw new Error("hyperparams 须为合法 JSON 对象");
      }
      return {
        title: form.title.trim(),
        objectives: form.objectives.trim(),
        variables: linesToList(form.variables || ""),
        controls: linesToList(form.controls || ""),
        success_criteria: linesToList(form.success_criteria || ""),
        record_fields: linesToList(form.record_fields || ""),
        notes: form.notes.trim(),
        status: form.status || "planned",
        claim_or_theorem_ref: form.claim_or_theorem_ref.trim() || null,
        revision_note: form.revision_note.trim(),
        hyperparams,
      };
    }
    return {
      title: form.title.trim(),
      verdict: form.verdict || "inconclusive",
      missing_data: linesToList(form.missing_data || ""),
      next_experiments: linesToList(form.next_experiments || ""),
      notes: form.notes.trim(),
      data_packet_id: form.data_packet_id.trim() || null,
      claim_ref: form.claim_ref.trim() || null,
    };
  }

  async function handleCreateSave() {
    if (!creatingType) return;
    setBusy(true);
    setFormError(null);
    try {
      const payload = buildPayload(creatingType);
      await create(creatingType, payload, sessionId);
      setCreatingType(null);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleEditSave(id: string, type: string) {
    if (type !== "ExperimentPlan" && type !== "NextStepMemo") return;
    setBusy(true);
    setFormError(null);
    try {
      const payload = buildPayload(type);
      const updated = await update(id, payload);
      setDetail(updated);
      setEditing(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确认删除该条目？")) return;
    setBusy(true);
    try {
      await remove(id);
      if (expandedId === id) {
        setExpandedId(null);
        setDetail(null);
      }
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`artifacts-panel${mode === "experiment-plans" ? " artifacts-panel--plans" : ""}`}>
      <div className="panel-toolbar">
        <strong>{title}</strong>
        <div className="panel-header-actions">
          {editableMode && (
            <>
              <button type="button" className="btn-ghost" onClick={() => startCreate("ExperimentPlan")}>
                新建计划
              </button>
              <button type="button" className="btn-ghost" onClick={() => startCreate("NextStepMemo")}>
                新建读数建议
              </button>
            </>
          )}
          <button type="button" className="btn-ghost" onClick={() => void refresh()} disabled={loading}>
            刷新
          </button>
        </div>
      </div>
      {mode === "experiment-plans" && artifacts.length > 0 && (
        <p className="panel-muted artifact-history-hint">
          历史计划 {planCount} 条
          {memoCount > 0 ? ` · 读数建议 ${memoCount} 条` : ""}
          （按时间倒序；对话产出与手工录入都会追加）
        </p>
      )}
      {error && <p className="panel-error">{error}</p>}
      {formError && <p className="panel-error">{formError}</p>}

      {creatingType && (
        <div className="artifact-editor">
          <h4>新建{TYPE_LABEL[creatingType]}</h4>
          <ArtifactFormFields type={creatingType} form={form} setForm={setForm} />
          <div className="import-actions">
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void handleCreateSave()}>
              {busy ? "保存中…" : "保存"}
            </button>
            <button type="button" className="btn-small" disabled={busy} onClick={() => setCreatingType(null)}>
              取消
            </button>
          </div>
        </div>
      )}

      {loading && artifacts.length === 0 && <p className="muted">加载中…</p>}
      {!loading && artifacts.length === 0 && !creatingType && (
        <p className="muted">{emptyHint ?? "暂无工件。对话中产出 artifact 围栏后会出现在此。"}</p>
      )}
      <ul className="artifact-list">
        {artifacts.map((a: ArtifactSummary) => {
          const open = expandedId === a.id;
          return (
            <li key={a.id} className={`artifact-item${open ? " artifact-item--open" : ""}`}>
              <button
                type="button"
                className="artifact-item-head"
                onClick={() => void loadDetail(a.id)}
                aria-expanded={open}
              >
                <span className="artifact-type">{TYPE_LABEL[a.type] ?? a.type}</span>
                <span className="artifact-title">{a.title || a.id}</span>
                <span className="artifact-meta muted">{formatWhen(a.created_at)}</span>
              </button>
              {open && (
                <div className="artifact-detail">
                  {detailLoading && <p className="muted">加载详情…</p>}
                  {!detailLoading && detail && editableMode && editing && (
                    <>
                      <ArtifactFormFields
                        type={a.type as "ExperimentPlan" | "NextStepMemo"}
                        form={form}
                        setForm={setForm}
                      />
                      <div className="import-actions">
                        <button
                          type="button"
                          className="btn-primary"
                          disabled={busy}
                          onClick={() => void handleEditSave(a.id, a.type)}
                        >
                          {busy ? "保存中…" : "保存"}
                        </button>
                        <button type="button" className="btn-small" onClick={() => setEditing(false)}>
                          取消
                        </button>
                      </div>
                    </>
                  )}
                  {!detailLoading && detail && !(editableMode && editing) && (
                    <>
                      <ArtifactDetailBody type={a.type} data={detail} />
                      {editableMode && (a.type === "ExperimentPlan" || a.type === "NextStepMemo") && (
                        <div className="import-actions">
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => startEdit(a.type, detail)}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            className="btn-small"
                            disabled={busy}
                            onClick={() => void handleDelete(a.id)}
                          >
                            删除
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ArtifactFormFields({
  type,
  form,
  setForm,
}: {
  type: "ExperimentPlan" | "NextStepMemo";
  form: Record<string, string>;
  setForm: (v: Record<string, string>) => void;
}) {
  const set = (key: string, value: string) => setForm({ ...form, [key]: value });
  if (type === "ExperimentPlan") {
    return (
      <div className="theorem-create-form">
        <label>
          标题
          <input value={form.title || ""} onChange={(e) => set("title", e.target.value)} />
        </label>
        <label>
          目标
          <textarea rows={3} value={form.objectives || ""} onChange={(e) => set("objectives", e.target.value)} />
        </label>
        <label>
          状态
          <select value={form.status || "planned"} onChange={(e) => set("status", e.target.value)}>
            <option value="planned">待做</option>
            <option value="active">进行中</option>
            <option value="done">已完成</option>
            <option value="superseded">已取代</option>
          </select>
        </label>
        <label>
          变量（一行一项）
          <textarea rows={3} value={form.variables || ""} onChange={(e) => set("variables", e.target.value)} />
        </label>
        <label>
          对照（一行一项）
          <textarea rows={3} value={form.controls || ""} onChange={(e) => set("controls", e.target.value)} />
        </label>
        <label>
          成功判据（一行一项）
          <textarea
            rows={3}
            value={form.success_criteria || ""}
            onChange={(e) => set("success_criteria", e.target.value)}
          />
        </label>
        <label>
          记录字段（一行一项）
          <textarea
            rows={3}
            value={form.record_fields || ""}
            onChange={(e) => set("record_fields", e.target.value)}
          />
        </label>
        <label>
          关联主张
          <input
            value={form.claim_or_theorem_ref || ""}
            onChange={(e) => set("claim_or_theorem_ref", e.target.value)}
          />
        </label>
        <label>
          超参 JSON
          <textarea rows={3} value={form.hyperparams || "{}"} onChange={(e) => set("hyperparams", e.target.value)} />
        </label>
        <label>
          修订说明
          <input value={form.revision_note || ""} onChange={(e) => set("revision_note", e.target.value)} />
        </label>
        <label>
          备注
          <textarea rows={3} value={form.notes || ""} onChange={(e) => set("notes", e.target.value)} />
        </label>
      </div>
    );
  }
  return (
    <div className="theorem-create-form">
      <label>
        标题
        <input value={form.title || ""} onChange={(e) => set("title", e.target.value)} />
      </label>
      <label>
        判读
        <select value={form.verdict || "inconclusive"} onChange={(e) => set("verdict", e.target.value)}>
          <option value="supported">supported</option>
          <option value="refuted">refuted</option>
          <option value="inconclusive">inconclusive</option>
        </select>
      </label>
      <label>
        缺数（一行一项）
        <textarea rows={3} value={form.missing_data || ""} onChange={(e) => set("missing_data", e.target.value)} />
      </label>
      <label>
        建议下一步（一行一项）
        <textarea
          rows={3}
          value={form.next_experiments || ""}
          onChange={(e) => set("next_experiments", e.target.value)}
        />
      </label>
      <label>
        DataPacket ID
        <input value={form.data_packet_id || ""} onChange={(e) => set("data_packet_id", e.target.value)} />
      </label>
      <label>
        关联主张
        <input value={form.claim_ref || ""} onChange={(e) => set("claim_ref", e.target.value)} />
      </label>
      <label>
        备注
        <textarea rows={3} value={form.notes || ""} onChange={(e) => set("notes", e.target.value)} />
      </label>
    </div>
  );
}

function ArtifactDetailBody({
  type,
  data,
}: {
  type: string;
  data: Record<string, unknown>;
}) {
  if (data._error) {
    return <p className="panel-error">{String(data._error)}</p>;
  }
  if (type === "ExperimentPlan") {
    const status = String(data.status || "planned");
    const vars = Array.isArray(data.variables) ? data.variables.map(String) : [];
    const controls = Array.isArray(data.controls) ? data.controls.map(String) : [];
    const criteria = Array.isArray(data.success_criteria)
      ? data.success_criteria.map(String)
      : [];
    const fields = Array.isArray(data.record_fields) ? data.record_fields.map(String) : [];
    return (
      <div className="artifact-plan-detail">
        <p>
          <span className={`artifact-status status-${status}`}>
            {STATUS_LABEL[status] ?? status}
          </span>
          {data.parent_plan_id ? (
            <span className="muted"> · 修订自 {String(data.parent_plan_id).slice(0, 8)}</span>
          ) : null}
        </p>
        {data.objectives ? (
          <p>
            <strong>目标</strong>：{String(data.objectives)}
          </p>
        ) : null}
        {data.claim_or_theorem_ref ? (
          <p>
            <strong>关联主张</strong>：{String(data.claim_or_theorem_ref)}
          </p>
        ) : null}
        {vars.length > 0 && (
          <p>
            <strong>变量</strong>：{vars.join("、")}
          </p>
        )}
        {controls.length > 0 && (
          <p>
            <strong>对照</strong>：{controls.join("、")}
          </p>
        )}
        {criteria.length > 0 && (
          <p>
            <strong>判据</strong>：{criteria.join("；")}
          </p>
        )}
        {fields.length > 0 && (
          <p>
            <strong>记录字段</strong>：{fields.join("、")}
          </p>
        )}
        {data.revision_note ? (
          <p>
            <strong>修订说明</strong>：{String(data.revision_note)}
          </p>
        ) : null}
        {data.notes ? (
          <p>
            <strong>备注</strong>：{String(data.notes)}
          </p>
        ) : null}
      </div>
    );
  }
  if (type === "NextStepMemo") {
    const missing = Array.isArray(data.missing_data) ? data.missing_data.map(String) : [];
    const next = Array.isArray(data.next_experiments)
      ? data.next_experiments.map(String)
      : [];
    return (
      <div className="artifact-plan-detail">
        <p>
          <strong>判读</strong>：{String(data.verdict || "inconclusive")}
        </p>
        {missing.length > 0 && (
          <p>
            <strong>缺数</strong>：{missing.join("；")}
          </p>
        )}
        {next.length > 0 && (
          <p>
            <strong>建议下一步</strong>：{next.join("；")}
          </p>
        )}
        {data.notes ? (
          <p>
            <strong>备注</strong>：{String(data.notes)}
          </p>
        ) : null}
      </div>
    );
  }
  if (type === "DerivationTrace") {
    const steps = Array.isArray(data.steps) ? data.steps : [];
    const l4 = Array.isArray(data.l4_ref_ids) ? data.l4_ref_ids.map(String) : [];
    const stepStatus: Record<string, string> = {
      proven: "已证",
      pending: "待验证",
      heuristic: "启发式",
    };
    return (
      <div className="artifact-plan-detail derivation-trace-detail">
        {l4.length > 0 && (
          <p>
            <strong>关联 L4</strong>：{l4.join("、")}
          </p>
        )}
        {data.claim_yaml ? (
          <pre className="claim-yaml-block">{String(data.claim_yaml)}</pre>
        ) : null}
        <ol className="derivation-step-list">
          {steps.map((raw, i) => {
            const step =
              raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
            const st = String(step.status || "pending");
            return (
              <li key={i} className={`derivation-step status-${st}`}>
                <div className="derivation-step-head">
                  <strong>{String(step.title || `步骤 ${i + 1}`)}</strong>
                  <span className={`artifact-status status-step-${st}`}>
                    {stepStatus[st] ?? st}
                  </span>
                </div>
                {step.body ? <p>{String(step.body)}</p> : null}
              </li>
            );
          })}
        </ol>
        {steps.length === 0 && <p className="muted">暂无推导步骤。</p>}
      </div>
    );
  }
  return (
    <pre className="artifact-raw-json">{JSON.stringify(data, null, 2).slice(0, 2000)}</pre>
  );
}

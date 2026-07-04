import type { ExperimentRun } from "../hooks/useExperimentLogs";

export interface ExperimentHighlight {
  label: string;
  value: string;
  tone?: "good" | "bad" | "warn" | "muted";
}

export interface ExperimentTierLine {
  name: string;
  statusLabel: string;
  message: string;
  tone: "good" | "bad" | "warn" | "muted";
}

export interface ExperimentCardView {
  id: string;
  title: string;
  statusLabel: string;
  tone: "good" | "bad" | "warn" | "muted";
  timeLabel: string;
  headline: string;
  highlights: ExperimentHighlight[];
  tiers: ExperimentTierLine[];
  notes: string[];
}

const RUN_STATUS: Record<string, { label: string; tone: ExperimentCardView["tone"] }> = {
  completed: { label: "完成", tone: "good" },
  pass: { label: "通过", tone: "good" },
  failed: { label: "失败", tone: "bad" },
  fail: { label: "失败", tone: "bad" },
  skipped: { label: "跳过", tone: "muted" },
};

const TIER_LABELS: Record<string, string> = {
  symbolic: "符号验证",
  numerical: "数值验证",
  experiment: "网络实验",
};

const SKIP_KEYS = new Set([
  "run_id",
  "log_path",
  "config_path",
  "verification",
  "claim",
  "details",
  "tiers",
  "created_at",
  "project_id",
  "session_id",
  "status",
  "name",
  "summary",
  "metrics",
]);

function tierTone(status: string): ExperimentTierLine["tone"] {
  if (status === "pass" || status === "completed") return "good";
  if (status === "fail" || status === "failed") return "bad";
  if (status === "skipped") return "muted";
  return "warn";
}

function tierStatusLabel(status: string): string {
  return RUN_STATUS[status]?.label ?? status;
}

function formatTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function friendlyConfigName(path: string): string | null {
  if (!path) return null;
  const base = path.split("/").pop() || path;
  return base.replace(/\.(yaml|yml|json)$/i, "");
}

function flattenMetrics(metrics: Record<string, unknown>): ExperimentHighlight[] {
  const rows: ExperimentHighlight[] = [];
  for (const [key, value] of Object.entries(metrics)) {
    if (value == null || typeof value === "object") continue;
    rows.push({
      label: metricLabel(key),
      value: formatPrimitive(value),
      tone: key.includes("loss") ? "muted" : undefined,
    });
  }
  return rows;
}

function metricLabel(key: string): string {
  const map: Record<string, string> = {
    loss: "损失",
    min_loss: "最小损失",
    max_loss: "最大损失",
    accuracy: "准确率",
    lr: "学习率",
  };
  return map[key] ?? key;
}

function formatPrimitive(value: unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, "");
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function extractSimpleSummary(summary: Record<string, unknown>): {
  headline: string;
  highlights: ExperimentHighlight[];
  tiers: ExperimentTierLine[];
  notes: string[];
} {
  if ("overall_passed" in summary || "tiers" in summary) {
    const passed = Boolean(summary.overall_passed);
    const claim = (summary.claim as Record<string, unknown> | undefined) ?? {};
    const expression = typeof claim.expression === "string" ? claim.expression : "";
    const tiersRaw = (summary.tiers as Record<string, Record<string, unknown>> | undefined) ?? {};
    const tiers: ExperimentTierLine[] = Object.entries(tiersRaw).map(([key, tier]) => {
      const status = String(tier.status ?? "unknown");
      const details = (tier.details as Record<string, unknown> | undefined) ?? {};
      const extra =
        typeof details.classification === "string"
          ? `，分类：${details.classification}`
          : typeof details.min_loss === "number"
            ? `，最小损失：${formatPrimitive(details.min_loss)}`
            : "";
      return {
        name: TIER_LABELS[key] ?? key,
        statusLabel: tierStatusLabel(status),
        message: `${String(tier.reason ?? "无说明")}${extra}`,
        tone: tierTone(status),
      };
    });
    const highlights: ExperimentHighlight[] = [];
    if (expression) {
      highlights.push({ label: "表达式", value: expression, tone: "muted" });
    }
    if (typeof claim.point === "string" && claim.point) {
      highlights.push({ label: "验证点", value: claim.point, tone: "muted" });
    }
    const expected = (claim.expected as Record<string, unknown> | undefined)?.classification;
    if (typeof expected === "string") {
      highlights.push({ label: "期望分类", value: expected, tone: "muted" });
    }
    return {
      headline: passed ? "数值验证通过" : "数值验证未通过",
      highlights,
      tiers,
      notes: [],
    };
  }

  if ("ok" in summary && Object.keys(summary).length <= 2) {
    const ok = Boolean(summary.ok);
    return {
      headline: ok ? "实验成功" : "实验失败",
      highlights: [],
      tiers: [],
      notes: [],
    };
  }

  const highlights: ExperimentHighlight[] = [];
  const notes: string[] = [];
  for (const [key, value] of Object.entries(summary)) {
    if (SKIP_KEYS.has(key) || value == null) continue;
    if (typeof value === "object") {
      notes.push(`${key}: 见下方分层结果`);
      continue;
    }
    highlights.push({
      label: metricLabel(key),
      value: formatPrimitive(value),
    });
  }
  return {
    headline: highlights.length ? "实验已记录" : "实验完成",
    highlights,
    tiers: [],
    notes,
  };
}

export function buildExperimentCard(run: ExperimentRun): ExperimentCardView {
  const summary = run.summary ?? {};
  const metrics = run.metrics ?? {};
  const statusMeta = RUN_STATUS[run.status] ?? { label: run.status || "未知", tone: "muted" as const };
  const parsed = extractSimpleSummary(summary);
  const configName = friendlyConfigName(run.config_path);

  const highlights = [...parsed.highlights, ...flattenMetrics(metrics)];
  if (configName) {
    highlights.unshift({ label: "配置", value: configName, tone: "muted" });
  }

  let title = run.name || configName || "未命名实验";
  if (title === "smoke") title = "Notebook 回传示例";
  if (title === "ui-upload") title = "Notebook 回传";

  return {
    id: run.run_id,
    title,
    statusLabel: statusMeta.label,
    tone: statusMeta.tone,
    timeLabel: formatTime(run.created_at),
    headline: parsed.headline,
    highlights,
    tiers: parsed.tiers,
    notes: parsed.notes,
  };
}

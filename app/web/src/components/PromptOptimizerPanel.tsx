import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";
import type { ChatMode } from "../utils/preferences";
import {
  POLISH_PRESETS,
  dispatchExportPreset,
} from "../utils/exportPresets";

export interface PromptStyleVariant {
  style_id: string;
  style_name: string;
  style_name_zh: string;
  prompt: string;
  scores: Record<string, number>;
  total_score: number;
  highlights: string[];
  recommended: boolean;
}

export interface PromptOptimizeResult {
  original: string;
  recommended_style_id: string;
  recommended_prompt: string;
  rationale: string;
  variants: PromptStyleVariant[];
  ai_applied: boolean;
  message: string;
}

export interface PromptTestCase {
  id: string;
  title: string;
  category: string;
  raw_prompt: string;
  context: string;
  expected_traits: string[];
  source_note: string;
}

interface PromptOptimizerPanelProps {
  open: boolean;
  initialText: string;
  mode: ChatMode;
  agent?: string | null;
  onClose: () => void;
  onApply: (text: string) => void;
  /** 选用导出润色体例时回调（同步产出 Tab 等） */
  onPolishPresetSelected?: (presetId: string) => void;
}

const SCORE_LABELS: Record<string, string> = {
  clarity: "清晰度",
  specificity: "具体性",
  verifiability: "可验证",
  structure: "结构性",
};

export function PromptOptimizerPanel({
  open,
  initialText,
  mode,
  agent,
  onClose,
  onApply,
  onPolishPresetSelected,
}: PromptOptimizerPanelProps) {
  const [text, setText] = useState(initialText);
  const [context, setContext] = useState("");
  const [goal, setGoal] = useState("更清晰可执行，但必须保持与原问同一主题，禁止编造未提及设定");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PromptOptimizeResult | null>(null);
  const [testCases, setTestCases] = useState<PromptTestCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [builtinPresetId, setBuiltinPresetId] = useState("");

  useEffect(() => {
    if (open) {
      setText(initialText);
      setBuiltinPresetId("");
    }
  }, [open, initialText]);

  useEffect(() => {
    if (!open) return;
    void (async () => {
      try {
        await waitForBackend();
        const res = await fetch("/v1/prompt/test-cases");
        if (res.ok) setTestCases((await res.json()) as PromptTestCase[]);
      } catch {
        /* 测试案例可选 */
      }
    })();
  }, [open]);

  const handleLoadCase = useCallback(() => {
    const picked = testCases.find((c) => c.id === selectedCaseId);
    if (!picked) return;
    setText(picked.raw_prompt);
    setContext(picked.context);
    setGoal(`满足：${picked.expected_traits.join("、")}`);
    setResult(null);
    setError(null);
  }, [selectedCaseId, testCases]);

  const handleApplyBuiltinPolish = () => {
    const preset = POLISH_PRESETS.find((p) => p.id === builtinPresetId);
    if (!preset) {
      setError("请先选择一种导出润色体例");
      return;
    }
    const filled =
      text.trim().length > 0
        ? `请按以下「${preset.label}」体例，润色整理下述内容：\n\n${text.trim()}\n\n—— 体例要求 ——\n${preset.text}`
        : `请按以下「${preset.label}」体例，润色整理当前课题/会话中的定理、推导与结论：\n\n${preset.text}`;
    dispatchExportPreset(preset.id);
    onPolishPresetSelected?.(preset.id);
    onApply(filled);
    onClose();
  };

  const handleOptimize = async () => {
    if (!text.trim()) {
      setError("请先输入待优化的提示词");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      await waitForBackend();
      const res = await fetch("/v1/prompt/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          context: context.trim(),
          goal: goal.trim(),
          mode,
          agent: agent && agent !== "auto" ? agent : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      setResult((await res.json()) as PromptOptimizeResult);
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="prompt-optimizer-overlay" onClick={onClose} role="presentation">
      <div
        className="prompt-optimizer-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="prompt-optimizer-title"
      >
        <header className="prompt-optimizer-head">
          <div>
            <h2 id="prompt-optimizer-title">优化提示词</h2>
            <p className="panel-muted">
              在<strong>不换题、不编造背景</strong>的前提下做多风格结构化改写；不合格结果会自动回退。
            </p>
          </div>
          <button type="button" className="btn-small" onClick={onClose}>
            关闭
          </button>
        </header>

        <div className="prompt-optimizer-body">
          <div className="prompt-optimizer-row">
            <label className="settings-label" htmlFor="prompt-builtin-polish">
              内置选项：笔记整理体例
            </label>
            <div className="prompt-case-row">
              <select
                id="prompt-builtin-polish"
                className="settings-input"
                value={builtinPresetId}
                onChange={(e) => {
                  setBuiltinPresetId(e.target.value);
                  setError(null);
                }}
              >
                <option value="">不使用（走下方 AI 对比）…</option>
                {POLISH_PRESETS.map((p) => (
                  <option key={p.id} value={p.id} title={p.hint}>
                    {p.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-small"
                disabled={!builtinPresetId}
                onClick={handleApplyBuiltinPolish}
                title="将体例填入输入框，并同步到产出导出面板"
              >
                采用体例
              </button>
            </div>
            {builtinPresetId && (
              <p className="panel-muted export-preset-hint">
                {POLISH_PRESETS.find((p) => p.id === builtinPresetId)?.hint}
              </p>
            )}
          </div>

          <div className="prompt-optimizer-row">
            <label className="settings-label" htmlFor="prompt-test-case">
              科研测试案例
            </label>
            <div className="prompt-case-row">
              <select
                id="prompt-test-case"
                className="settings-input"
                value={selectedCaseId}
                onChange={(e) => setSelectedCaseId(e.target.value)}
              >
                <option value="">选择案例快速填充…</option>
                {testCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    [{c.category}] {c.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-small"
                disabled={!selectedCaseId}
                onClick={handleLoadCase}
              >
                加载
              </button>
            </div>
          </div>

          <label className="settings-label" htmlFor="prompt-raw">
            原始提示词
          </label>
          <textarea
            id="prompt-raw"
            className="settings-input export-ai-input"
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入你想发送给 AI 的原始问题…"
          />

          <label className="settings-label" htmlFor="prompt-context">
            补充语境（可选）
          </label>
          <textarea
            id="prompt-context"
            className="settings-input"
            rows={2}
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="课题背景、已有假设（仅限真实信息；勿写会诱导编造的空泛故事）"
          />

          <label className="settings-label" htmlFor="prompt-goal">
            优化目标
          </label>
          <textarea
            id="prompt-goal"
            className="settings-input"
            rows={2}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />

          <div className="prompt-optimizer-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void handleOptimize()}
              disabled={loading || !text.trim()}
            >
              {loading ? "对比生成中…" : "生成多风格对比"}
            </button>
            <span className="panel-muted">
              当前模式：{mode === "math" ? "Math" : "Chat"}
              {agent && agent !== "auto" ? ` · Agent: ${agent}` : ""}
            </span>
          </div>

          {error && <p className="panel-error">{error}</p>}

          {result && (
            <div className="prompt-optimizer-result">
              <p className="prompt-rationale">
                <strong>推荐：</strong>
                {result.rationale || result.message}
                {!result.ai_applied && (
                  <span className="panel-muted">（模板回退）</span>
                )}
              </p>

              <ul className="prompt-variant-list">
                {result.variants.map((v) => (
                  <li
                    key={v.style_id}
                    className={`prompt-variant-card${v.recommended ? " recommended" : ""}`}
                  >
                    <div className="prompt-variant-head">
                      <div>
                        <strong>{v.style_name_zh}</strong>
                        <span className="panel-muted"> · {v.style_name}</span>
                        {v.recommended && <span className="prompt-rec-badge">推荐</span>}
                      </div>
                      <span className="prompt-score-total">{v.total_score}/40</span>
                    </div>
                    <div className="prompt-score-bars">
                      {Object.entries(v.scores).map(([k, val]) => (
                        <span key={k} className="prompt-score-chip">
                          {SCORE_LABELS[k] ?? k}: {val}
                        </span>
                      ))}
                    </div>
                    {v.highlights.length > 0 && (
                      <p className="panel-muted prompt-highlights">
                        {v.highlights.join(" · ")}
                      </p>
                    )}
                    <pre className="prompt-variant-text">{v.prompt}</pre>
                    <button
                      type="button"
                      className="btn-small btn-primary"
                      onClick={() => {
                        onApply(v.prompt);
                        onClose();
                      }}
                    >
                      采用此版本
                    </button>
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="btn-secondary btn-block"
                onClick={() => {
                  onApply(result.recommended_prompt);
                  onClose();
                }}
              >
                采用推荐版本
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

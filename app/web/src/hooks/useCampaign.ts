import { useCallback, useEffect, useState } from "react";
import { formatBackendError, waitForBackend } from "../utils/backend";

export interface ResearchCampaign {
  id: string;
  project_id: string;
  title: string;
  task_family: string;
  current_stage: string;
  status: "active" | "blocked" | "done" | "iterate";
  gates: Record<string, string>;
  stage_artifacts: Record<string, unknown>;
  assumptions: string[];
}

const STAGE_ORDER = [
  "S0_campaign",
  "S1_literature",
  "S2_formalization",
  "S3_theory",
  "S4_counterexample",
  "S5_experiment",
  "S6_synthesis",
  "S7_review",
  "S8_archive",
  "complete",
];

export function stageProgress(stage: string, status?: string): number {
  // 已完成课题应显示 100%；仅停在 S8_archive 时旧逻辑算成 90%，看起来像「卡在收尾」
  if (status === "done" || stage === "complete" || stage === "S8_archive") {
    return 100;
  }
  const idx = STAGE_ORDER.indexOf(stage);
  if (idx < 0) return 0;
  return Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
}

export function useCampaign(projectId: string, enabled: boolean) {
  const [campaign, setCampaign] = useState<ResearchCampaign | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      await waitForBackend();
      const res = await fetch(`/v1/projects/${encodeURIComponent(projectId)}/campaign`);
      if (res.status === 404) {
        setCampaign(null);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setCampaign(await res.json());
    } catch (err) {
      setError(formatBackendError(err));
    } finally {
      setLoading(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const applyCampaignUpdate = useCallback((payload: string) => {
    try {
      const data = JSON.parse(payload) as Partial<ResearchCampaign> & {
        campaign_id?: string;
      };
      setCampaign((prev) => {
        if (!prev && !data.campaign_id) return prev;
        return {
          id: data.campaign_id ?? prev?.id ?? "",
          project_id: data.project_id ?? prev?.project_id ?? projectId,
          title: prev?.title ?? "",
          task_family: prev?.task_family ?? "",
          current_stage: data.current_stage ?? prev?.current_stage ?? "S0_campaign",
          status: (data.status as ResearchCampaign["status"]) ?? prev?.status ?? "active",
          gates: data.gates ?? prev?.gates ?? {},
          stage_artifacts: prev?.stage_artifacts ?? {},
          assumptions: prev?.assumptions ?? [],
        };
      });
    } catch {
      /* ignore malformed SSE */
    }
  }, [projectId]);

  return {
    campaign,
    loading,
    error,
    refresh,
    applyCampaignUpdate,
    progress: campaign ? stageProgress(campaign.current_stage, campaign.status) : 0,
  };
}

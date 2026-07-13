export type WorkbenchTab = "literature" | "theory" | "verify" | "output";

export function pipelineStageToTab(stage: string): WorkbenchTab | null {
  const s = stage.toLowerCase();
  if (s.includes("literature") || s.includes("文献") || s.includes("rag")) return "literature";
  if (
    s.includes("theory") ||
    s.includes("理论") ||
    s.includes("derive") ||
    s.includes("formalization") ||
    s.includes("counterexample") ||
    s.includes("反例") ||
    s.includes("graph") ||
    s.includes("图谱")
  ) {
    return "theory";
  }
  if (s.includes("verify") || s.includes("验证")) return "verify";
  if (
    s.includes("experiment") ||
    s.includes("实验") ||
    s.includes("numerical") ||
    s.includes("synthesis") ||
    s.includes("review") ||
    s.includes("campaign") ||
    s.includes("complete") ||
    s.includes("archive") ||
    s.includes("export") ||
    s.includes("导出")
  ) {
    return "output";
  }
  return null;
}

import type { DocumentInfo } from "../hooks/useDocuments";
import type { ExperimentRun, ExperimentRunUpdate } from "../hooks/useExperimentLogs";
import type { AgentQualityItem, ObservabilitySummary } from "../hooks/useObservability";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import type { VerificationDashboard } from "../hooks/useVerification";
import type { VerificationRecord } from "../hooks/useVerificationRecords";
import type { RagRef } from "../hooks/useRagRefs";
import type { WorkbenchTab } from "../utils/workbenchTabs";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { DocumentPanel } from "./DocumentPanel";
import { ExperimentLogPanel, type NotebookUploadPayload, type ExperimentFileUploadMeta } from "./ExperimentLogPanel";
import { ExportPanel } from "./ExportPanel";
import { ObservabilityPanel } from "./ObservabilityPanel";
import { RagRefsPanel } from "./RagRefsPanel";
import { TheoremLibraryPanel } from "./TheoremLibraryPanel";
import { VerificationDashboardPanel } from "./VerificationDashboard";
import { WorkbenchSection } from "./WorkbenchSection";

interface ResearchWorkbenchProps {
  sessionId: string;
  projectId: string;
  disabled?: boolean;
  activeTab: WorkbenchTab;
  onTabChange: (tab: WorkbenchTab) => void;
  /** 界面版本允许的工作台 Tab；默认全开 */
  allowedTabs?: WorkbenchTab[];
  structuredEntries: StructuredMemoryEntry[];
  structuredLoading: boolean;
  structuredError: string | null;
  onRefreshStructured: () => void;
  onSelectTheorem: (entry: StructuredMemoryEntry) => void;
  onCreateTheorem?: (payload: {
    kind: string;
    title: string;
    body: string;
  }) => Promise<void>;
  onOpenMarkdownImport?: () => void;
  onOpenPdfImport?: () => void;
  experimentRuns: ExperimentRun[];
  experimentLoading: boolean;
  experimentError: string | null;
  onRefreshExperiments: () => void;
  onJupyterUpload: (payload: NotebookUploadPayload) => Promise<void>;
  onExperimentFileUpload?: (file: File, meta: ExperimentFileUploadMeta) => Promise<void>;
  onUpdateExperimentRun?: (runId: string, patch: ExperimentRunUpdate) => Promise<void>;
  onDeleteExperimentRun?: (runId: string) => Promise<void>;
  documents: DocumentInfo[];
  documentsLoading: boolean;
  documentsUploading: boolean;
  documentsError: string | null;
  onRefreshDocuments: () => void;
  onUploadDocument: (content: string, title?: string) => Promise<boolean>;
  onUploadFile?: (file: File, title?: string) => Promise<boolean>;
  onIngestArxiv?: (arxivId: string, title?: string) => Promise<boolean>;
  onDeleteDocument: (docId: string) => Promise<boolean>;
  onClearAllDocuments?: () => Promise<boolean>;
  ragRefs: RagRef[];
  ragRefsLoading: boolean;
  ragRefsError: string | null;
  onRefreshRagRefs: () => void;
  verificationDashboard: VerificationDashboard | null;
  verificationLoading: boolean;
  verificationError: string | null;
  verificationRecords: VerificationRecord[];
  verificationRecordsLoading: boolean;
  onRefreshVerification: () => void;
  onRefreshVerificationRecords: () => void;
  onRunVerification: (claim: Record<string, unknown>) => Promise<unknown>;
  observabilitySummary: ObservabilitySummary | null;
  agentQuality: AgentQualityItem[];
  observabilityLoading: boolean;
  observabilityError: string | null;
  onRefreshObservability: () => void;
  /** SSE artifact_saved 时递增，触发 ArtifactsPanel 刷新 */
  artifactsRefreshToken?: number;
}

const ALL_TABS: { id: WorkbenchTab; label: string; hint: string }[] = [
  { id: "literature", label: "文献", hint: "上传与检索" },
  { id: "theory", label: "理论", hint: "定理与推导" },
  { id: "verify", label: "验证", hint: "检验与质量" },
  { id: "output", label: "产出", hint: "实验与导出" },
];

const DEFAULT_ALLOWED: WorkbenchTab[] = ["literature", "theory", "verify", "output"];

export function ResearchWorkbench(props: ResearchWorkbenchProps) {
  const { sessionId, projectId, disabled, activeTab, onTabChange } = props;
  const allowed = props.allowedTabs?.length ? props.allowedTabs : DEFAULT_ALLOWED;
  const tabs = ALL_TABS.filter((t) => allowed.includes(t.id));

  return (
    <aside className="research-workbench" aria-label="科研工作台">
      <header className="workbench-header">
        <div>
          <h2>科研工作台</h2>
          <p className="workbench-subtitle">
            {tabs.find((t) => t.id === activeTab)?.hint ?? "按研究阶段查看"}
          </p>
        </div>
      </header>
      <nav className="workbench-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={activeTab === t.id}
            className={activeTab === t.id ? "workbench-tab active" : "workbench-tab"}
            onClick={() => onTabChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <div className="workbench-body">
        {activeTab === "literature" && allowed.includes("literature") && (
          <>
            <WorkbenchSection title="文献库" defaultOpen badge={props.documents.length || undefined}>
              <DocumentPanel
                documents={props.documents}
                loading={props.documentsLoading}
                uploading={props.documentsUploading}
                error={props.documentsError}
                disabled={disabled}
                onRefresh={props.onRefreshDocuments}
                onUpload={props.onUploadDocument}
                onUploadFile={props.onUploadFile}
                onIngestArxiv={props.onIngestArxiv}
                onDelete={props.onDeleteDocument}
                onClearAll={props.onClearAllDocuments}
              />
            </WorkbenchSection>
            <WorkbenchSection title="检索引用">
              <RagRefsPanel
                refs={props.ragRefs}
                loading={props.ragRefsLoading}
                error={props.ragRefsError}
                onRefresh={props.onRefreshRagRefs}
                disabled={disabled}
              />
            </WorkbenchSection>
          </>
        )}
        {activeTab === "theory" && allowed.includes("theory") && (
          <>
            <WorkbenchSection title="推导迹" defaultOpen>
              <ArtifactsPanel
                projectId={projectId}
                sessionId={sessionId}
                types={["DerivationTrace"]}
                title="推导迹"
                emptyHint="Theory Agent 在推导时输出 artifact:DerivationTrace 围栏后会出现在此：分步证明、待验证标记、关联定理。"
                refreshToken={props.artifactsRefreshToken}
              />
            </WorkbenchSection>
            <WorkbenchSection
              title="定理库"
              defaultOpen
              badge={props.structuredEntries.length || undefined}
            >
              <TheoremLibraryPanel
                entries={props.structuredEntries}
                loading={props.structuredLoading}
                error={props.structuredError}
                onRefresh={props.onRefreshStructured}
                onSelect={props.onSelectTheorem}
                onCreate={props.onCreateTheorem}
                onOpenMarkdownImport={props.onOpenMarkdownImport}
                onOpenPdfImport={props.onOpenPdfImport}
              />
            </WorkbenchSection>
          </>
        )}
        {activeTab === "verify" && allowed.includes("verify") && (
          <>
            <WorkbenchSection title="验证看板" defaultOpen>
              <VerificationDashboardPanel
                dashboard={props.verificationDashboard}
                records={props.verificationRecords}
                loading={props.verificationLoading}
                recordsLoading={props.verificationRecordsLoading}
                error={props.verificationError}
                sessionId={sessionId}
                projectId={projectId}
                onRefresh={props.onRefreshVerification}
                onRefreshRecords={props.onRefreshVerificationRecords}
                onRunVerification={props.onRunVerification}
              />
            </WorkbenchSection>
            <WorkbenchSection title="可观测性">
              <ObservabilityPanel
                summary={props.observabilitySummary}
                agentQuality={props.agentQuality}
                loading={props.observabilityLoading}
                error={props.observabilityError}
                onRefresh={props.onRefreshObservability}
              />
            </WorkbenchSection>
          </>
        )}
        {activeTab === "output" && allowed.includes("output") && (
          <>
            <WorkbenchSection title="实验计划" defaultOpen>
              <ArtifactsPanel
                projectId={projectId}
                sessionId={sessionId}
                types={["ExperimentPlan", "NextStepMemo"]}
                title="实验计划 / 下一步"
                emptyHint="Experiment Agent 输出计划或下一步备忘后显示于此。"
                mode="experiment-plans"
                refreshToken={props.artifactsRefreshToken}
              />
            </WorkbenchSection>
            <WorkbenchSection title="实验记录" defaultOpen>
              <ExperimentLogPanel
                runs={props.experimentRuns}
                loading={props.experimentLoading}
                error={props.experimentError}
                sessionId={sessionId}
                projectId={projectId}
                onRefresh={props.onRefreshExperiments}
                onJupyterUpload={props.onJupyterUpload}
                onExperimentFileUpload={props.onExperimentFileUpload}
                onUpdateRun={props.onUpdateExperimentRun}
                onDeleteRun={props.onDeleteExperimentRun}
              />
            </WorkbenchSection>
            <WorkbenchSection title="课题笔记导出" defaultOpen>
              <ExportPanel sessionId={sessionId} projectId={projectId} />
            </WorkbenchSection>
          </>
        )}
      </div>
    </aside>
  );
}

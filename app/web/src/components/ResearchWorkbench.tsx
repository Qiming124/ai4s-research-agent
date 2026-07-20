import type { DagEdge, DagNode } from "../hooks/useAssumptionDag";
import type { DocumentInfo } from "../hooks/useDocuments";
import type { ExperimentRun } from "../hooks/useExperimentLogs";
import type { MemoryEdge } from "../hooks/useMemoryGraph";
import type { AgentQualityItem, ObservabilitySummary } from "../hooks/useObservability";
import type { StructuredMemoryEntry } from "../hooks/useStructuredMemory";
import type { VerificationDashboard } from "../hooks/useVerification";
import type { VerificationRecord } from "../hooks/useVerificationRecords";
import type { RagRef } from "../hooks/useRagRefs";
import type { WorkspaceFile } from "../hooks/useWorkspaceFiles";
import type { WorkbenchTab } from "../utils/workbenchTabs";
import { AssumptionDagPanel } from "./AssumptionDagPanel";
import { DocumentPanel } from "./DocumentPanel";
import { ExperimentLogPanel } from "./ExperimentLogPanel";
import { ExportPanel } from "./ExportPanel";
import { KnowledgeGraphPanel } from "./KnowledgeGraphPanel";
import { ObservabilityPanel } from "./ObservabilityPanel";
import { RagRefsPanel } from "./RagRefsPanel";
import { TheoremLibraryPanel } from "./TheoremLibraryPanel";
import { TheoryAssetsPanel } from "./TheoryAssetsPanel";
import { VerificationDashboardPanel } from "./VerificationDashboard";
import { WorkbenchSection } from "./WorkbenchSection";
import { WorkspacePanel } from "./WorkspacePanel";

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
  graphNodes: StructuredMemoryEntry[];
  graphEdges: MemoryEdge[];
  graphLoading: boolean;
  graphError: string | null;
  onRefreshGraph: () => void;
  experimentRuns: ExperimentRun[];
  experimentLoading: boolean;
  experimentError: string | null;
  onRefreshExperiments: () => void;
  onRunExperiment: () => Promise<void>;
  onJupyterTemplate: () => Promise<void>;
  onJupyterUpload: () => Promise<void>;
  workspaceFiles: WorkspaceFile[];
  workspaceLoading: boolean;
  workspaceError: string | null;
  onRefreshWorkspace: () => void;
  theorySymbols: string;
  theoryAssumptions: string;
  theoryMatrix: string;
  theoryAssetsLoading: boolean;
  theoryAssetsError: string | null;
  onRefreshTheoryAssets: () => void;
  dagNodes: DagNode[];
  dagEdges: DagEdge[];
  dagLoading: boolean;
  dagError: string | null;
  onRefreshDag: () => void;
  onDagImpact: (id: string) => Promise<unknown>;
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
              />
            </WorkbenchSection>
            <WorkbenchSection title="理论资产">
              <TheoryAssetsPanel
                symbols={props.theorySymbols}
                assumptions={props.theoryAssumptions}
                matrix={props.theoryMatrix}
                loading={props.theoryAssetsLoading}
                error={props.theoryAssetsError}
                onRefresh={props.onRefreshTheoryAssets}
              />
            </WorkbenchSection>
            <WorkbenchSection title="假设依赖图" badge={props.dagNodes.length || undefined}>
              <AssumptionDagPanel
                nodes={props.dagNodes}
                edges={props.dagEdges}
                loading={props.dagLoading}
                error={props.dagError}
                onRefresh={props.onRefreshDag}
                onImpact={props.onDagImpact}
              />
            </WorkbenchSection>
            <WorkbenchSection title="关系图谱" badge={props.graphNodes.length || undefined}>
              <KnowledgeGraphPanel
                nodes={props.graphNodes}
                edges={props.graphEdges}
                loading={props.graphLoading}
                error={props.graphError}
                onRefresh={props.onRefreshGraph}
                onSelectNode={props.onSelectTheorem}
              />
            </WorkbenchSection>
            <WorkbenchSection title="工作区文件" badge={props.workspaceFiles.length || undefined}>
              <WorkspacePanel
                files={props.workspaceFiles}
                loading={props.workspaceLoading}
                error={props.workspaceError}
                onRefresh={props.onRefreshWorkspace}
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
            <WorkbenchSection
              title="数值实验"
              defaultOpen
              badge={props.experimentRuns.length || undefined}
            >
              <ExperimentLogPanel
                runs={props.experimentRuns}
                loading={props.experimentLoading}
                error={props.experimentError}
                onRefresh={props.onRefreshExperiments}
                onRunExperiment={props.onRunExperiment}
                onJupyterTemplate={props.onJupyterTemplate}
                onJupyterUpload={props.onJupyterUpload}
              />
            </WorkbenchSection>
            <WorkbenchSection title="论文导出" defaultOpen>
              <ExportPanel sessionId={sessionId} projectId={projectId} />
            </WorkbenchSection>
          </>
        )}
      </div>
    </aside>
  );
}

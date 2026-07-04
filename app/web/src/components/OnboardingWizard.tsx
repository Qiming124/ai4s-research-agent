const ONBOARDING_KEY = "ai4s_onboarding_done";

interface OnboardingWizardProps {
  onComplete: () => void;
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const handleDone = () => {
    localStorage.setItem(ONBOARDING_KEY, "1");
    onComplete();
  };

  return (
    <div className="onboarding-overlay" role="dialog" aria-label="首次使用向导">
      <div className="onboarding-card">
        <h2>欢迎使用 AI4S 科研工作台 v2.0</h2>
        <ol className="onboarding-steps">
          <li>
            <strong>选择课题</strong> — 左栏「课题」Tab 新建/切换课题，会话自动关联。
          </li>
          <li>
            <strong>上传文献</strong> — 右侧「文献」Tab：PDF/DOCX/arXiv 一键导入。
          </li>
          <li>
            <strong>对话研究</strong> — 中间对话区发送问题或点「完整研究」；流水线自动切换 Tab。
          </li>
          <li>
            <strong>理论推导</strong> — 「理论」Tab 查看定理库、假设图、关系图谱与工作区。
          </li>
          <li>
            <strong>验证与产出</strong> — 「验证」Tab 重跑验证；「产出」Tab 实验记录与导出 MD/Word/PDF。
          </li>
          <li>
            <strong>任务看板</strong> — 左栏「任务」Tab 管理课题待办（待办/进行中/完成）。
          </li>
        </ol>
        <button type="button" className="btn-primary" onClick={handleDone}>
          开始使用
        </button>
      </div>
    </div>
  );
}

export function shouldShowOnboarding(): boolean {
  return !localStorage.getItem(ONBOARDING_KEY);
}

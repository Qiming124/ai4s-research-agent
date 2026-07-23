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
        <h2>欢迎使用 AI4S 理论侧多智能体 v2.2</h2>
        <p className="onboarding-edition-note">
          用深度学习做科学问题的理论侧协作：读文献、推导、实验建议与数据解读（不代跑训练）。
          损失函数局部极小等为示范课题。界面为科研工作台（文献 / 理论 / 产出）。
        </p>
        <ol className="onboarding-steps">
          <li>
            <strong>选择课题</strong> — 左栏会话树中展开课题文件夹，新建课题/会话；会话挂在课题下。
          </li>
          <li>
            <strong>文献</strong> — 右侧「文献」Tab：检索讨论或 PDF/DOCX/arXiv 入库；用 literature Agent 做方法提炼。
          </li>
          <li>
            <strong>理论推导</strong> — 选 theory（或 Math 模式）对话推导；「理论」Tab 查看定理库与推导迹。
          </li>
          <li>
            <strong>实验建议与数据</strong> — 选 experiment 获取实验计划（历史会累积保存）；将结果回传到「产出」后，可请顾问解读并生成修订计划。
          </li>
          <li>
            <strong>产出</strong> — 「产出」Tab：实验记录与导出 MD/Word/PDF；可用「优化提示词」内的导出润色体例。
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

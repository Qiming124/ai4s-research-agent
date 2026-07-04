import type { CotStep } from "../utils/cotParse";
import { MarkdownContent } from "./MarkdownContent";

interface CotStepsPanelProps {
  steps: CotStep[];
}

/** 外显结构化思维链（最终回答中的分步小节） */
export function CotStepsPanel({ steps }: CotStepsPanelProps) {
  if (!steps.length) return null;

  return (
    <div className="cot-steps-panel">
      <div className="cot-steps-title">思维链</div>
      <ol className="cot-steps-list">
        {steps.map((step) => (
          <li key={`${step.step}-${step.title}`} className="cot-step-item">
            <div className="cot-step-header">
              <span className="cot-step-num">{step.step}</span>
              <strong>{step.title}</strong>
            </div>
            <div className="cot-step-body">
              <MarkdownContent content={step.body} className="cot-step-md" />
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

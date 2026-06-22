import { Component, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import type { PluggableList } from "unified";
import { preprocessMathContent } from "../utils/preprocessMath";

interface MarkdownContentProps {
  content: string;
  className?: string;
  /** 流式生成中：纯文本显示，避免半成品 LaTeX 触发 KaTeX 报错 */
  isStreaming?: boolean;
}

const MAX_MARKDOWN_CHARS = 12000;

const remarkPlugins: PluggableList = [remarkMath, remarkGfm];
const rehypePlugins: PluggableList = [
  [rehypeKatex, { strict: "ignore", errorColor: "#b45309" }],
];

function safePreprocess(content: string): string {
  try {
    return preprocessMathContent(content);
  } catch {
    return content;
  }
}

class MarkdownGuard extends Component<
  { processed: string; className: string },
  { failed: boolean }
> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override componentDidCatch(error: Error) {
    console.warn("Markdown/KaTeX render failed, using plain text:", error.message);
  }

  override render() {
    if (this.state.failed) {
      return (
        <pre className={`message-plain ${this.props.className}`.trim()}>
          {this.props.processed}
        </pre>
      );
    }

    return (
      <div className={`markdown-body ${this.props.className}`}>
        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
          {this.props.processed}
        </ReactMarkdown>
      </div>
    );
  }
}

function PlainText({ content, className }: { content: string; className: string }) {
  return <pre className={`message-plain ${className}`.trim()}>{content}</pre>;
}

/** Markdown + GFM + LaTeX（KaTeX）；流式阶段纯文本 */
export function MarkdownContent({
  content,
  className = "",
  isStreaming = false,
}: MarkdownContentProps) {
  const safeClass = className.trim();

  const processed = useMemo(() => {
    if (!content || isStreaming) return content ?? "";
    if (content.length > MAX_MARKDOWN_CHARS) return content;
    return safePreprocess(content);
  }, [content, isStreaming]);

  if (!content) return null;

  if (isStreaming) {
    return <PlainText content={content} className={`streaming-plain ${safeClass}`} />;
  }

  if (content.length > MAX_MARKDOWN_CHARS) {
    return <PlainText content={content} className={safeClass} />;
  }

  return <MarkdownGuard processed={processed} className={safeClass} />;
}

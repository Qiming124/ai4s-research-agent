import { Component } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownContentProps {
  content: string;
  className?: string;
  /** 流式生成中：纯文本显示 */
  isStreaming?: boolean;
}

const MAX_MARKDOWN_CHARS = 12000;
const remarkPlugins = [remarkGfm];

class MarkdownGuard extends Component<
  { content: string; className: string },
  { failed: boolean }
> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override componentDidCatch(error: Error) {
    console.warn("Markdown render failed, using plain text:", error.message);
  }

  override render() {
    if (this.state.failed) {
      return (
        <pre className={`message-plain ${this.props.className}`.trim()}>
          {this.props.content}
        </pre>
      );
    }

    return (
      <div className={`markdown-body ${this.props.className}`}>
        <ReactMarkdown remarkPlugins={remarkPlugins}>
          {this.props.content}
        </ReactMarkdown>
      </div>
    );
  }
}

function PlainText({ content, className }: { content: string; className: string }) {
  return (
    <pre className={`message-plain ${className}`.trim()}>{content}</pre>
  );
}

/** 消息正文：流式纯文本；结束后轻量 GFM（无 KaTeX/高亮，避免栈溢出） */
export function MarkdownContent({
  content,
  className = "",
  isStreaming = false,
}: MarkdownContentProps) {
  const safeClass = className.trim();

  if (!content) return null;

  if (isStreaming) {
    return <PlainText content={content} className={`streaming-plain ${safeClass}`} />;
  }

  // 超长内容直接纯文本，避免 markdown 解析过深
  if (content.length > MAX_MARKDOWN_CHARS) {
    return <PlainText content={content} className={safeClass} />;
  }

  return <MarkdownGuard content={content} className={safeClass} />;
}

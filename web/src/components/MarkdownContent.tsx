import { useEffect, useRef, type RefObject } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import { preprocessMathContent } from "../utils/preprocessMath";
import "highlight.js/styles/github.min.css";

interface MarkdownContentProps {
  content: string;
  className?: string;
  /** 流式生成中：纯文本显示，避免半成品 LaTeX 触发 KaTeX 报错 */
  isStreaming?: boolean;
}

/** 为 KaTeX 仍无法解析的公式添加友好提示 */
function useKatexErrorHints(
  containerRef: RefObject<HTMLDivElement | null>,
  deps: string,
) {
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    for (const el of root.querySelectorAll(".katex-error")) {
      if (el.getAttribute("data-hint-applied")) continue;
      el.setAttribute("data-hint-applied", "true");
      el.setAttribute("title", "公式语法不完整或无法解析，以下为原文");
    }
  }, [deps, containerRef]);
}

/** Markdown 渲染（GFM + LaTeX + 代码高亮） */
export function MarkdownContent({
  content,
  className = "",
  isStreaming = false,
}: MarkdownContentProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const processed =
    content && !isStreaming ? preprocessMathContent(content) : (content ?? "");

  useKatexErrorHints(containerRef, processed);

  if (!content) return null;

  if (isStreaming) {
    return (
      <pre className={`streaming-plain ${className}`.trim()}>{content}</pre>
    );
  }

  return (
    <div ref={containerRef} className={`markdown-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[
          [rehypeKatex, { strict: "ignore", errorColor: "#b45309" }],
          rehypeHighlight,
        ]}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}

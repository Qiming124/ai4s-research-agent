import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.min.css";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

/** Markdown 渲染（GFM + LaTeX + 代码高亮） */
export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  if (!content) return null;

  return (
    <div className={`markdown-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

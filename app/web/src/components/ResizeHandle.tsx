import { useCallback } from "react";

interface ResizeHandleProps {
  direction: "horizontal" | "vertical";
  onResize: (delta: number) => void;
  className?: string;
  title?: string;
}

export function ResizeHandle({
  direction,
  onResize,
  className = "",
  title = "拖拽调整大小",
}: ResizeHandleProps) {
  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      let last = direction === "horizontal" ? e.clientX : e.clientY;

      const onMove = (ev: MouseEvent) => {
        const pos = direction === "horizontal" ? ev.clientX : ev.clientY;
        const delta = pos - last;
        last = pos;
        if (delta !== 0) onResize(delta);
      };

      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.body.style.cursor = direction === "horizontal" ? "col-resize" : "row-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [direction, onResize],
  );

  return (
    <div
      role="separator"
      aria-orientation={direction === "horizontal" ? "vertical" : "horizontal"}
      aria-label={title}
      className={`resize-handle resize-${direction} ${className}`.trim()}
      onMouseDown={onMouseDown}
      title={title}
    />
  );
}

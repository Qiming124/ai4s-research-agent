import { useCallback, useState } from "react";
import {
  adjustLayoutPrefs,
  loadLayoutPrefs,
  resetLayoutPrefs,
  type LayoutPrefs,
} from "../utils/layoutPrefs";

export function useLayoutPrefs() {
  const [prefs, setPrefs] = useState<LayoutPrefs>(loadLayoutPrefs);

  const resizeLeft = useCallback((delta: number) => {
    setPrefs((current) =>
      adjustLayoutPrefs(current, { leftWidth: current.leftWidth + delta }),
    );
  }, []);

  const resizeRight = useCallback((delta: number) => {
    setPrefs((current) =>
      adjustLayoutPrefs(current, { rightWidth: current.rightWidth - delta }),
    );
  }, []);

  const resizeSidebarProject = useCallback((delta: number) => {
    setPrefs((current) =>
      adjustLayoutPrefs(current, {
        sidebarProjectHeight: current.sidebarProjectHeight + delta,
      }),
    );
  }, []);

  const resizeSidebarTask = useCallback((delta: number) => {
    setPrefs((current) =>
      adjustLayoutPrefs(current, { sidebarTaskHeight: current.sidebarTaskHeight + delta }),
    );
  }, []);

  const reset = useCallback(() => {
    setPrefs(resetLayoutPrefs());
  }, []);

  return {
    prefs,
    resizeLeft,
    resizeRight,
    resizeSidebarProject,
    resizeSidebarTask,
    reset,
  };
}

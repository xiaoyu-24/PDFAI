import { useEffect, useRef } from "react";

interface AutoRefreshOptions {
  enabled?: boolean;
  intervalMs?: number;
}

export function useAutoRefresh(
  refresh: () => void | Promise<unknown>,
  { enabled = true, intervalMs = 2000 }: AutoRefreshOptions = {}
) {
  const refreshRef = useRef(refresh);
  const runningRef = useRef(false);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled) return;

    const runRefresh = async () => {
      if (document.visibilityState !== "visible" || runningRef.current) return;
      runningRef.current = true;
      try {
        await refreshRef.current();
      } finally {
        runningRef.current = false;
      }
    };
    const handleFocus = () => void runRefresh();
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") void runRefresh();
    };
    const timer = window.setInterval(() => void runRefresh(), intervalMs);
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled, intervalMs]);
}

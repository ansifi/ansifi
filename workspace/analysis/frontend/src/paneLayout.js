import { useCallback, useEffect, useState } from "react";

export const SIDEBAR_MIN = 180;
export const SIDEBAR_MAX = 560;
export const CHAT_MIN = 260;
export const CHAT_MAX = 720;
export const EDITOR_MIN = 280;
export const CHAT_HEIGHT_MIN = 200;
export const DEFAULTS = { sidebar: 260, chat: 360, chatHeight: 320 };

const KEYS = {
  sidebar: "coding-agent.sidebarWidth",
  chat: "coding-agent.chatWidth",
  chatHeight: "coding-agent.chatHeight",
};

function readStored(key, fallback) {
  try {
    const n = Number(window.localStorage.getItem(key));
    if (Number.isFinite(n) && n >= 80) return Math.round(n);
  } catch {
    /* ignore */
  }
  return fallback;
}

function writeStored(key, value) {
  try {
    window.localStorage.setItem(key, String(Math.round(value)));
  } catch {
    /* ignore */
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function layoutFromWidth(width) {
  if (width <= 720) return "narrow";
  if (width <= 1100) return "tablet";
  return "wide";
}

export function usePaneLayout() {
  const [layout, setLayout] = useState(() =>
    typeof window === "undefined" ? "wide" : layoutFromWidth(window.innerWidth)
  );
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    typeof window === "undefined" ? DEFAULTS.sidebar : readStored(KEYS.sidebar, DEFAULTS.sidebar)
  );
  const [chatWidth, setChatWidth] = useState(() =>
    typeof window === "undefined" ? DEFAULTS.chat : readStored(KEYS.chat, DEFAULTS.chat)
  );
  const [chatHeight, setChatHeight] = useState(() =>
    typeof window === "undefined" ? DEFAULTS.chatHeight : readStored(KEYS.chatHeight, DEFAULTS.chatHeight)
  );

  useEffect(() => {
    const onResize = () => setLayout(layoutFromWidth(window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => writeStored(KEYS.sidebar, sidebarWidth), [sidebarWidth]);
  useEffect(() => writeStored(KEYS.chat, chatWidth), [chatWidth]);
  useEffect(() => writeStored(KEYS.chatHeight, chatHeight), [chatHeight]);

  const beginDrag = useCallback(
    (kind, event, bodyEl) => {
      event.preventDefault();
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const startY = event.clientY;
      const startSidebar = sidebarWidth;
      const startChat = chatWidth;
      const startChatH = chatHeight;
      const stacked = layout !== "wide";
      const target = event.currentTarget;
      target.setPointerCapture?.(pointerId);
      document.body.classList.add("pane-resizing");
      document.body.dataset.paneAxis = kind === "chatHeight" ? "y" : "x";

      const move = (ev) => {
        if (ev.buttons !== undefined && ev.buttons === 0) return;
        const box = bodyEl?.getBoundingClientRect();
        const width = box?.width || window.innerWidth;
        const height = box?.height || window.innerHeight;
        const x = ev.clientX;
        const y = ev.clientY;
        if (kind === "sidebar") {
          const reserved = stacked ? EDITOR_MIN + 16 : startChat + EDITOR_MIN + 16;
          const max = Math.min(SIDEBAR_MAX, width - reserved);
          setSidebarWidth(clamp(startSidebar + (x - startX), SIDEBAR_MIN, Math.max(SIDEBAR_MIN, max)));
        } else if (kind === "chat") {
          const max = Math.min(CHAT_MAX, width - startSidebar - EDITOR_MIN - 16);
          setChatWidth(clamp(startChat - (x - startX), CHAT_MIN, Math.max(CHAT_MIN, max)));
        } else if (kind === "chatHeight") {
          const max = Math.min(height * 0.7, height - 180);
          setChatHeight(clamp(startChatH - (y - startY), CHAT_HEIGHT_MIN, Math.max(CHAT_HEIGHT_MIN, max)));
        }
      };

      const stop = () => {
        try {
          target.releasePointerCapture?.(pointerId);
        } catch {
          /* ignore */
        }
        document.body.classList.remove("pane-resizing");
        delete document.body.dataset.paneAxis;
        window.removeEventListener("pointermove", move);
        window.removeEventListener("mousemove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("mouseup", stop);
        window.removeEventListener("pointercancel", stop);
      };

      window.addEventListener("pointermove", move);
      window.addEventListener("mousemove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("mouseup", stop);
      window.addEventListener("pointercancel", stop);
    },
    [sidebarWidth, chatWidth, chatHeight, layout]
  );

  const reset = useCallback((kind) => {
    if (kind === "sidebar") setSidebarWidth(DEFAULTS.sidebar);
    if (kind === "chat") setChatWidth(DEFAULTS.chat);
    if (kind === "chatHeight") setChatHeight(DEFAULTS.chatHeight);
  }, []);

  const gridStyle =
    layout === "wide"
      ? {
          gridTemplateColumns: `${sidebarWidth}px 6px minmax(${EDITOR_MIN}px, 1fr) 6px ${chatWidth}px`,
          gridTemplateRows: "minmax(0, 1fr)",
        }
      : layout === "tablet"
        ? {
            gridTemplateColumns: `${sidebarWidth}px 6px minmax(0, 1fr)`,
            gridTemplateRows: `minmax(0, 1fr) 6px ${chatHeight}px`,
          }
        : {
            gridTemplateColumns: "1fr",
            gridTemplateRows: `minmax(140px, 28%) minmax(0, 1fr) 6px ${chatHeight}px`,
          };

  return { layout, sidebarWidth, chatWidth, chatHeight, gridStyle, beginDrag, reset };
}

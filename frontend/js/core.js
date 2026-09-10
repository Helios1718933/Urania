/* ============================================================
   core.js —— 共享状态与基础工具
   无内部依赖；被 components / views / app 共同引用。
   ============================================================ */

export const $main = document.getElementById("main");
export const $chip = document.getElementById("unlearned-chip");
export const $toast = document.getElementById("toast");

/** 全局可变状态（视图相关，刷新即丢） */
export const state = {
  view: "draw",
  config: null,       // /api/config 结果（掌握度标签等）
  drawPoint: null,    // 当前抽到的知识点
  remaining: 0,       // 剩余未学习数
  phase: "recall",    // draw 视图阶段: "recall"(回忆门) | "revealed"(已揭晓)
};

/** 回忆门时限（秒），到时自动揭晓 */
export const RECALL_SECONDS = 120;

/* ---------------- 基础工具 ---------------- */

export function esc(s) {
  // 转义服务端数据，防止注入破坏 DOM
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 401) {
    // 局域网模式下令牌失效（换设备 / 清过 Cookie）→ 回根路径显示口令页
    window.location.href = "/";
    throw new Error("需要重新输入访问口令");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `请求失败 (${res.status})`);
  return data;
}

let toastTimer = null;
export function toast(msg) {
  $toast.textContent = msg;
  $toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $toast.hidden = true; }, 2200);
}

/* ---------------- 领域格式化 ---------------- */

export function masteryLabel(level) {
  return (state.config?.mastery_labels ?? {})[String(level)] ?? `掌握度 ${level}`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

export function fmtClock(s) {
  const m = Math.floor(s / 60), ss = s % 60;
  return `${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

/* ---------------- 顶栏 ---------------- */

/** 刷新顶部的「未学习 N」计数胶囊 */
export async function refreshChip() {
  try {
    const s = await api("/api/stats");
    $chip.textContent = `未学习 ${s.unlearned}`;
  } catch { /* 静默失败即可，不打断主流程 */ }
}

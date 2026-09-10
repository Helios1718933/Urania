/* ============================================================
   app.js —— 入口：装配视图、绑定全局事件、启动
   模块划分：
     core.js        共享状态与基础工具（api / 转义 / 领域格式化）
     components.js  可复用 HTML 片段（纯函数）
     router.js      视图注册与切换
     views/*.js     各视图渲染
   ============================================================ */

import { api, refreshChip, state } from "./core.js";
import { registerView, setHooks, switchView } from "./router.js";
import { clearRecallTimer, renderDraw, revealDraw } from "./views/draw.js";
import { renderReviewList } from "./views/review.js";
import { renderStats } from "./views/stats.js";

/* ---------------- 视图注册 ---------------- */

registerView("draw", renderDraw);
registerView("review", renderReviewList);
registerView("stats", renderStats);

setHooks({
  beforeSwitch: () => clearRecallTimer(),   // 离开抽取页时停掉回忆倒计时
  afterSwitch: () => refreshChip(),
});

/* ---------------- 全局事件 ---------------- */

document.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

// 空状态里的跳转按钮
document.addEventListener("click", (e) => {
  const goto = e.target.closest("[data-goto]")?.dataset.goto;
  if (goto) switchView(goto);
});

// 快捷键：抽取视图下 R 换一个；回忆阶段空格立即揭晓
document.addEventListener("keydown", (e) => {
  if (state.view !== "draw") return;
  const tag = document.activeElement?.tagName;
  if (tag === "BUTTON" || tag === "INPUT" || tag === "TEXTAREA" || tag === "A") return;
  if (e.key === "r" || e.key === "R") {
    e.preventDefault();
    renderDraw();
  } else if ((e.key === " " || e.key === "Spacebar") && state.phase === "recall") {
    e.preventDefault();
    revealDraw();
  }
});

/* ---------------- 启动 ---------------- */

(async function init() {
  try {
    state.config = await api("/api/config");
  } catch {
    state.config = null; // 标签缺失时使用兜底文案
  }
  switchView("draw");
})();

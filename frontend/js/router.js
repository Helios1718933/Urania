/* ============================================================
   router.js —— 视图注册与切换
   只做「名字 → 渲染函数」的登记与切换，不认识任何具体视图，
   避免 views 与 router 互相引用的循环依赖。
   ============================================================ */

import { state } from "./core.js";

const views = new Map();
let hooks = { beforeSwitch: null, afterSwitch: null };

/** 注册视图渲染函数（由 app.js 在启动时调用） */
export function registerView(name, render) {
  views.set(name, render);
}

/** 设置切换前后钩子（如停掉回忆门倒计时、刷新顶部计数） */
export function setHooks({ beforeSwitch, afterSwitch } = {}) {
  if (beforeSwitch !== undefined) hooks.beforeSwitch = beforeSwitch;
  if (afterSwitch !== undefined) hooks.afterSwitch = afterSwitch;
}

/** 同步分段控件的选中态与无障碍属性 */
function syncSegmented(name) {
  document.querySelectorAll(".seg-btn").forEach((b) => {
    const active = b.dataset.view === name;
    b.classList.toggle("is-active", active);
    b.setAttribute("aria-selected", String(active));
  });
}

export function switchView(name) {
  if (hooks.beforeSwitch) hooks.beforeSwitch(name);
  state.view = name;
  syncSegmented(name);
  const render = views.get(name);
  if (render) render();
  if (hooks.afterSwitch) hooks.afterSwitch(name);
}

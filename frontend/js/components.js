/* ============================================================
   components.js —— 可复用的 HTML 片段（纯函数，无副作用）
   依赖 core 的转义与领域格式化；被各视图引用。
   ============================================================ */

import { esc, fmtDate, masteryLabel } from "./core.js";
import { icons } from "./icons.js";

/** 掌握度圆点（5 档，4 档以上变绿） */
export function masteryDots(m) {
  const dots = [1, 2, 3, 4, 5]
    .map((i) => `<i class="${i <= m ? "on" : ""}"></i>`).join("");
  return `<span class="mastery-dots ${m >= 4 ? "m4" : ""}" title="${esc(masteryLabel(m))}">${dots}</span>`;
}

/** 列表右侧的状态徽章（到期 / 已掌握 / 排期） */
export function statusBadge(point) {
  if (point.is_due) return `<span class="badge badge-due">今天该复习</span>`;
  if (point.status === "mastered") return `<span class="badge badge-mastered">已掌握</span>`;
  return `<span class="badge badge-scheduled">${fmtDate(point.next_review_at)}</span>`;
}

/** 可视化区：http(s) 链接渲染成外链，否则当文字说明 */
export function vizBlock(point) {
  const v = String(point.visualization || "").trim();
  if (!v) return "";
  if (/^https?:\/\//i.test(v)) {
    return `<div class="viz"><a class="viz-link" href="${esc(v)}" target="_blank" rel="noopener">`
      + `查看可视化讲解 ${icons.external}</a></div>`;
  }
  return `<div class="viz"><span class="viz-note">可视化 · ${esc(v)}</span></div>`;
}

export function tagsBlock(point) {
  if (!point.tags?.length) return "";
  return `<div class="tags">${point.tags.map((t) => `<span class="tag"># ${esc(t)}</span>`).join("")}</div>`;
}

export function principleBlock(point) {
  return `<div class="draw-principle">${esc(point.principle || "（暂无原理讲解）")}</div>`;
}

/** 从 markdown 围栏里取出代码正文（没有围栏就原样用） */
export function stripFence(raw) {
  const text = String(raw || "").trim();
  const match = text.match(/^```[a-zA-Z]*\n([\s\S]*?)\n?```$/);
  return match ? match[1] : text;
}

/** 代码块（带拷贝按钮；拷贝逻辑在 app.js 的事件委托里） */
export function codeBlock(raw) {
  const code = stripFence(raw);
  if (!code) return "";
  return `
    <div class="code-wrap">
      <div class="code-head">
        <span class="code-lang">代码示例</span>
        <button class="code-copy" type="button" data-copy>拷贝</button>
      </div>
      <pre class="code-block"><code>${esc(code)}</code></pre>
    </div>`;
}

/** 学习元信息：难度 / 来源 / 自测关卡 */
export function metaBlock(point) {
  const bits = [];
  if (point.difficulty > 0) {
    const filled = "★".repeat(Math.min(5, point.difficulty));
    const empty = "☆".repeat(Math.max(0, 5 - point.difficulty));
    bits.push(`<span class="kp-diff" title="难度 ${point.difficulty}/5">${filled}${empty}</span>`);
  }
  if (point.source) bits.push(`<span class="kp-source">来源 · ${esc(point.source)}</span>`);
  if (point.self_test) bits.push(`<span class="kp-selftest">自测 · ${esc(point.self_test)}</span>`);
  return bits.length ? `<div class="kp-meta">${bits.join("")}</div>` : "";
}

/**
 * 知识点正文：优先渲染四段式（定义 / 机制 / 要点 / 代码）；
 * 没有结构化字段时回退到 principle 段落（手写条目的旧路径）。
 */
export function structuredBlock(point) {
  const hasStructure = !!(point.mechanism || point.key_point || point.code_example);
  if (!hasStructure) {
    return `<div class="kp">${principleBlock(point)}</div>`;
  }
  return `
    <div class="kp">
      ${point.definition ? `<p class="kp-def">${esc(point.definition)}</p>` : ""}
      ${point.mechanism ? `<p class="kp-mech">${esc(point.mechanism)}</p>` : ""}
      ${point.key_point
        ? `<div class="kp-key"><span class="kp-key-label">面试 / 实战</span>${esc(point.key_point)}</div>`
        : ""}
      ${codeBlock(point.code_example)}
      ${metaBlock(point)}
    </div>`;
}

/**
 * 空状态卡片。
 * @param {keyof typeof icons} icon  图标名（见 icons.js，替代 emoji）
 * 注意：title/desc 会转义；actionHTML 是前端自己写的受控片段，直接透传。
 */
export function emptyBox(icon, title, desc, actionHTML = "") {
  return `
    <div class="empty">
      <div class="empty-icon">${icons[icon] ?? ""}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(desc)}</p>
      ${actionHTML}
    </div>`;
}

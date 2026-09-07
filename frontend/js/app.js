/* ============================================================
   Urania 前端逻辑（原生 JS，无框架、无依赖）
   视图：draw（抽取）/ review（复习列表 + 详情）/ stats（统计）
   ============================================================ */
"use strict";

const $main = document.getElementById("main");
const $chip = document.getElementById("unlearned-chip");
const $toast = document.getElementById("toast");

const state = {
  view: "draw",
  config: null,       // /api/config 结果（掌握度标签等）
  drawPoint: null,    // 当前抽到的知识点
  remaining: 0,       // 剩余未学习数
};

/* ---------------- 工具 ---------------- */

function esc(s) {
  // 转义服务端数据，防止注入破坏 DOM
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `请求失败 (${res.status})`);
  return data;
}

let toastTimer = null;
function toast(msg) {
  $toast.textContent = msg;
  $toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $toast.hidden = true; }, 2200);
}

function masteryLabel(level) {
  return (state.config?.mastery_labels ?? {})[String(level)] ?? `掌握度 ${level}`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

function masteryDots(m) {
  const dots = [1, 2, 3, 4, 5]
    .map((i) => `<i class="${i <= m ? "on" : ""}"></i>`).join("");
  return `<span class="mastery-dots ${m >= 4 ? "m4" : ""}" title="${esc(masteryLabel(m))}">${dots}</span>`;
}

function vizBlock(point) {
  const v = String(point.visualization || "").trim();
  if (!v) return "";
  if (/^https?:\/\//i.test(v)) {
    return `<div class="viz"><a class="viz-link" href="${esc(v)}" target="_blank" rel="noopener">查看可视化讲解 ↗</a></div>`;
  }
  return `<div class="viz"><span class="viz-note">可视化 · ${esc(v)}</span></div>`;
}

function tagsBlock(point) {
  if (!point.tags?.length) return "";
  return `<div class="tags">${point.tags.map((t) => `<span class="tag"># ${esc(t)}</span>`).join("")}</div>`;
}

function principleBlock(point) {
  return `<div class="draw-principle">${esc(point.principle || "（暂无原理讲解）")}</div>`;
}

/* ---------------- 视图切换 ---------------- */

document.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".seg-btn").forEach((b) => {
    const active = b.dataset.view === view;
    b.classList.toggle("is-active", active);
    b.setAttribute("aria-selected", String(active));
  });
  if (view === "draw") renderDraw();
  else if (view === "review") renderReviewList();
  else if (view === "stats") renderStats();
  refreshChip();
}

/* ---------------- 顶部未学习计数 ---------------- */

async function refreshChip() {
  try {
    const s = await api("/api/stats");
    $chip.textContent = `未学习 ${s.unlearned}`;
  } catch { /* 静默失败即可 */ }
}

/* ================= 抽取视图 ================= */

async function renderDraw() {
  $main.innerHTML = `<p class="loading">正在抽取…</p>`;
  let data;
  try {
    data = await api("/api/draw");
  } catch (e) {
    $main.innerHTML = emptyBox("⚠️", "加载失败", e.message);
    return;
  }
  state.drawPoint = data.point;
  state.remaining = data.remaining;

  if (!data.point) {
    $main.innerHTML = `
      <section class="view">
        ${emptyBox("🎉", "全部知识点都已进入学习循环",
          "没有可抽取的未学习知识点了，去复习巩固一下吧。",
          `<button class="btn btn-primary" data-goto="review">去复习</button>`)}
      </section>`;
    return;
  }

  const p = data.point;
  $main.innerHTML = `
    <section class="view">
      <p class="view-caption">随机抽取一个未学习的知识点 · 还剩 ${data.remaining} 个未学习</p>
      <article class="card draw-card">
        <div><span class="pill pill-blue">${esc(p.category)}</span></div>
        <h2 class="draw-name">${esc(p.name)}</h2>
        ${principleBlock(p)}
        ${vizBlock(p)}
        ${tagsBlock(p)}
        <div class="divider"></div>
        <div class="draw-actions" id="draw-actions">
          <button class="btn btn-primary" id="btn-learn">标记为已学习</button>
          <button class="btn btn-secondary" id="btn-redraw">换一个</button>
          <span class="kbd-hint">快捷键 <kbd>R</kbd> 换一个</span>
        </div>
        <div class="mastery-picker" id="mastery-picker" hidden>
          <p>你现在的掌握程度是？</p>
          <div class="picker-row">
            ${[1, 2, 3].map((m) => `
              <button class="picker-opt" data-mastery="${m}">
                <strong>${esc(masteryLabel(m).split(" · ")[0])}</strong>
                <span>${esc(masteryLabel(m).split(" · ")[1] || "")}</span>
              </button>`).join("")}
          </div>
        </div>
      </article>
    </section>`;

  document.getElementById("btn-learn").addEventListener("click", () => {
    document.getElementById("mastery-picker").hidden = false;
    document.getElementById("btn-learn").disabled = true;
  });
  document.getElementById("btn-redraw").addEventListener("click", renderDraw);
  document.querySelectorAll("#mastery-picker .picker-opt").forEach((opt) => {
    opt.addEventListener("click", async () => {
      const mastery = Number(opt.dataset.mastery);
      try {
        await api(`/api/points/${p.id}/learn`, {
          method: "POST",
          body: JSON.stringify({ mastery }),
        });
        toast(`已标记：${p.name}（${masteryLabel(mastery).split(" · ")[0]}）`);
        renderDraw();
        refreshChip();
      } catch (e) {
        toast(e.message);
      }
    });
  });
}

/* ================= 复习视图 ================= */

async function renderReviewList() {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let data;
  try {
    data = await api("/api/review/queue");
  } catch (e) {
    $main.innerHTML = emptyBox("⚠️", "加载失败", e.message);
    return;
  }

  if (!data.items.length) {
    $main.innerHTML = `
      <section class="view">
        ${emptyBox("🗂", "还没有已学习的知识点", "先去抽取一个新知识点，标记学习后就会出现在这里。",
          `<button class="btn btn-primary" data-goto="draw">去抽取新知识</button>`)}
      </section>`;
    return;
  }

  const dueCount = data.items.filter((x) => x.is_due).length;
  const rows = data.items.map((p) => `
    <div class="list-row" data-id="${p.id}" role="button" tabindex="0">
      <div class="row-main">
        <div class="row-name">${esc(p.name)}</div>
        <div class="row-sub">${esc(p.category)} · 已复习 ${p.review_count} 次</div>
      </div>
      <div class="row-side">
        ${masteryDots(p.mastery)}
        ${p.is_due
          ? `<span class="badge badge-due">今天该复习</span>`
          : p.status === "mastered"
            ? `<span class="badge badge-mastered">已掌握</span>`
            : `<span class="badge badge-scheduled">${fmtDate(p.next_review_at)}</span>`}
      </div>
      <span class="chevron">›</span>
    </div>`).join("");

  $main.innerHTML = `
    <section class="view">
      <p class="view-caption">已学习的知识点 · 共 ${data.items.length} 个${dueCount ? `，其中 ${dueCount} 个今天该复习` : ""}</p>
      <div class="list-group">${rows}</div>
    </section>`;

  document.querySelectorAll(".list-row").forEach((row) => {
    const open = () => renderReviewDetail(Number(row.dataset.id));
    row.addEventListener("click", open);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });
}

async function renderReviewDetail(pointId) {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let point;
  try {
    point = (await api(`/api/points/${pointId}`)).point;
  } catch (e) {
    $main.innerHTML = emptyBox("⚠️", "加载失败", e.message);
    return;
  }

  $main.innerHTML = `
    <section class="view">
      <button class="back-btn" id="btn-back">‹ 返回复习列表</button>
      <article class="card draw-card">
        <div class="detail-meta">
          <span class="pill pill-blue">${esc(point.category)}</span>
          ${point.status === "mastered" ? `<span class="badge badge-mastered">已掌握</span>` : ""}
        </div>
        <h2 class="draw-name">${esc(point.name)}</h2>
        <p class="detail-mastery">
          ${masteryDots(point.mastery)}&nbsp;&nbsp;${esc(masteryLabel(point.mastery))}
          · 已复习 ${point.review_count} 次 · 上次复习 ${fmtDate(point.last_reviewed_at)}
        </p>
        <div class="divider"></div>
        ${principleBlock(point)}
        ${vizBlock(point)}
        ${tagsBlock(point)}
        <div class="divider"></div>
        <div class="rating-group">
          <p>凭记忆回想一遍，诚实自评：</p>
          <div class="rating-row">
            <button class="btn btn-rate-forgot" data-rating="forgot">忘了</button>
            <button class="btn btn-rate-fuzzy" data-rating="fuzzy">有点模糊</button>
            <button class="btn btn-rate-solid" data-rating="solid">记住了</button>
          </div>
        </div>
        <div class="danger-zone">
          <button class="btn-text-danger" id="btn-reset">重置为未学习</button>
        </div>
      </article>
    </section>`;

  document.getElementById("btn-back").addEventListener("click", renderReviewList);
  document.querySelectorAll(".rating-row .btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const rating = btn.dataset.rating;
      try {
        const r = await api(`/api/points/${point.id}/review`, {
          method: "POST",
          body: JSON.stringify({ rating }),
        });
        toast(`${r.point.name} · ${masteryLabel(r.point.mastery)}，下次 ${fmtDate(r.point.next_review_at)}`);
        renderReviewDetail(point.id);
        refreshChip();
      } catch (e) {
        toast(e.message);
      }
    });
  });
  document.getElementById("btn-reset").addEventListener("click", async () => {
    if (!window.confirm(`确定把「${point.name}」重置为未学习吗？学习记录将被清除。`)) return;
    try {
      await api(`/api/points/${point.id}/record`, { method: "DELETE" });
      toast("已重置为未学习");
      renderReviewList();
      refreshChip();
    } catch (e) {
      toast(e.message);
    }
  });
}

/* ================= 统计视图 ================= */

async function renderStats() {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let s;
  try {
    s = await api("/api/stats");
  } catch (e) {
    $main.innerHTML = emptyBox("⚠️", "加载失败", e.message);
    return;
  }

  const total = Math.max(1, s.total);
  const pct = Math.round((s.learned / total) * 100);
  const R = 48, C = 2 * Math.PI * R;
  const distMax = Math.max(1, ...Object.values(s.mastery_distribution));
  const distRows = Object.entries(s.mastery_distribution).map(([lv, n]) => `
    <div class="dist-row lv${lv}">
      <span class="dist-label">${esc(masteryLabel(Number(lv)))}</span>
      <div class="dist-bar-track"><div class="dist-bar" style="width: ${(n / distMax) * 100}%"></div></div>
      <span class="dist-count">${n}</span>
    </div>`).join("");

  $main.innerHTML = `
    <section class="view">
      <p class="view-caption">学习进度总览</p>
      <div class="stats-hero">
        <div class="ring-wrap">
          <svg width="108" height="108" viewBox="0 0 108 108">
            <circle class="ring-track" cx="54" cy="54" r="${R}" fill="none" stroke-width="10"/>
            <circle class="ring-value" cx="54" cy="54" r="${R}" fill="none" stroke-width="10"
              stroke-linecap="round" stroke-dasharray="${C}"
              stroke-dashoffset="${C * (1 - s.learned / total)}"/>
          </svg>
          <div class="ring-label"><strong>${pct}%</strong><span>已开始学习</span></div>
        </div>
        <div class="stats-nums">
          <div class="stat-num"><div class="n c-blue">${s.unlearned}</div><div class="l">未学习</div></div>
          <div class="stat-num"><div class="n">${s.learning}</div><div class="l">学习中</div></div>
          <div class="stat-num"><div class="n c-green">${s.mastered}</div><div class="l">已掌握</div></div>
          <div class="stat-num"><div class="n c-orange">${s.due}</div><div class="l">今天该复习</div></div>
          <div class="stat-num"><div class="n">${s.total}</div><div class="l">知识点总数</div></div>
          <div class="stat-num"><div class="n">${s.total_reviews}</div><div class="l">累计复习次数</div></div>
        </div>
      </div>
      <div class="dist-card">
        <h3>掌握度分布（已学习的 ${s.learned} 个知识点）</h3>
        ${s.learned ? distRows : `<p class="view-caption">还没有已学习的知识点。</p>`}
      </div>
    </section>`;
}

/* ---------------- 空状态 / 通用 ---------------- */

function emptyBox(icon, title, desc, actionHTML = "") {
  return `
    <div class="empty">
      <div class="empty-icon">${icon}</div>
      <h3>${esc(title)}</h3>
      <p>${esc(desc)}</p>
      ${actionHtmlSafe(actionHtml)}
    </div>`;
}

// emptyBox 的标题/描述走 esc；操作按钮是前端自己写的受控 HTML，直接透传
function actionHtmlSafe(html) { return html; }

document.addEventListener("click", (e) => {
  const goto = e.target.closest("[data-goto]")?.dataset.goto;
  if (goto) switchView(goto);
});

// 快捷键：抽取视图下按 R 换一个
document.addEventListener("keydown", (e) => {
  if (state.view !== "draw") return;
  const tag = document.activeElement?.tagName;
  if (tag === "BUTTON" || tag === "INPUT" || tag === "TEXTAREA" || tag === "A") return;
  if (e.key === "r" || e.key === "R") {
    e.preventDefault();
    renderDraw();
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

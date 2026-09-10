/* ============================================================
   views/stats.js —— 统计视图（进度环 + 计数 + 掌握度分布）
   ============================================================ */

import { $main, api, esc, masteryLabel } from "../core.js";
import { emptyBox } from "../components.js";

export async function renderStats() {
  $main.innerHTML = `<p class="loading">载入中…</p>`;
  let s;
  try {
    s = await api("/api/stats");
  } catch (e) {
    $main.innerHTML = emptyBox("alert", "加载失败", e.message);
    return;
  }

  const total = Math.max(1, s.total);
  const pct = Math.round((s.learned / total) * 100);
  const R = 48;
  const C = 2 * Math.PI * R;
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
          <svg width="108" height="108" viewBox="0 0 108 108" role="img"
               aria-label="已开始学习 ${pct}%">
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

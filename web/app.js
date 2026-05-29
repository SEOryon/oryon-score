(() => {
  const form = document.getElementById("scoreForm");
  const input = document.getElementById("urlInput");
  const btn = document.getElementById("scoreBtn");
  const out = document.getElementById("result");

  const fmtBucket = (key) =>
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const escapeHtml = (s) => String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const renderError = (msg) => {
    out.classList.remove("hidden");
    out.innerHTML = `<div class="error-card">${msg}</div>`;
  };

  const renderResult = (r) => {
    const tone = r.score >= 70 ? "" : r.score >= 50 ? "warn" : "danger";
    const buckets = Object.entries(r.bucket_scores)
      .map(([k, v]) => `
        <div class="bucket-row">
          <div class="bucket-name">${fmtBucket(k)}</div>
          <div class="bucket-bar"><div class="bucket-fill" style="width:${v.percent}%"></div></div>
          <div class="bucket-pts">${v.earned}/${v.max}</div>
        </div>`).join("");

    const failed = r.signals.filter((s) => !s.passed);
    const passed = r.signals.filter((s) => s.passed);

    const fixHtml = failed
      .slice()
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 8)
      .map((s) => `
        <div class="fix-item">
          <div class="icon">✗</div>
          <div>
            <div class="name">${escapeHtml(s.name)}</div>
            <div class="desc">${escapeHtml(s.detail)}</div>
            ${s.fix ? `<div class="desc fix" style="margin-top:6px;">→ ${escapeHtml(s.fix)}</div>` : ""}
          </div>
        </div>`).join("");

    const passHtml = passed
      .slice(0, 6)
      .map((s) => `
        <div class="fix-item">
          <div class="icon ok">✓</div>
          <div>
            <div class="name">${escapeHtml(s.name)}</div>
            <div class="desc">${escapeHtml(s.detail)}</div>
          </div>
        </div>`).join("");

    const notesHtml = (r.notes && r.notes.length)
      ? `<div class="notice">${r.notes.map(n => `<div>${escapeHtml(n)}</div>`).join("")}</div>`
      : "";

    out.classList.remove("hidden");
    out.innerHTML = `
      <div class="score-card">
        <div class="score-header">
          <div>
            <div class="url-label">${escapeHtml(r.url)}</div>
            ${r.page_title ? `<div class="page-title">${escapeHtml(r.page_title)}</div>` : ""}
          </div>
          <div style="text-align:right;">
            <div class="score-big ${tone}">${r.score}<span style="font-size:36px;opacity:0.6;">/100</span></div>
            <div class="grade-pill">Grade ${r.grade}</div>
          </div>
        </div>
        ${notesHtml}
        <div class="buckets">${buckets}</div>
      </div>

      ${fixHtml ? `<div class="section-title">Top fixes <span style="font-size:14px;font-weight:500;color:var(--ink-muted);">(ranked by impact)</span></div><div class="fix-list">${fixHtml}</div>` : ""}
      ${passHtml ? `<div class="section-title">What's working</div><div class="fix-list">${passHtml}</div>` : ""}
    `;
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const run = async (url) => {
    btn.disabled = true;
    btn.textContent = "Scoring…";
    out.classList.remove("hidden");
    out.innerHTML = `<div class="score-card" style="text-align:center;padding:48px;"><div class="score-big">…</div><div style="margin-top:12px;color:var(--ink-muted);font-family:'Geist Mono',monospace;font-size:13px;">fetching · parsing · scoring</div></div>`;
    try {
      const resp = await fetch(`/api/score?url=${encodeURIComponent(url)}`);
      const data = await resp.json();
      if (!resp.ok || data.error) {
        renderError(data.error || `HTTP ${resp.status}`);
      } else {
        renderResult(data);
      }
    } catch (e) {
      renderError(String(e));
    } finally {
      btn.disabled = false;
      btn.textContent = "Score it →";
    }
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = input.value.trim();
    if (!v) return;
    run(v);
  });

  // Allow URL prefill via ?url=
  const params = new URLSearchParams(window.location.search);
  const prefill = params.get("url");
  if (prefill) {
    input.value = prefill;
    run(prefill);
  }
})();

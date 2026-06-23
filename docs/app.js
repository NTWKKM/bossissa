/**
 * app.js — SIP Analysis Frontend
 * Fetches tableone.json + metadata.json and renders the interactive page.
 */

const DATA_BASE = "./data";

// ─────────────────────────────────────────────────────────────────
// Data fetch
// ─────────────────────────────────────────────────────────────────
async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

// ─────────────────────────────────────────────────────────────────
// Render hero summary cards
// ─────────────────────────────────────────────────────────────────
function renderMeta(meta) {
  document.getElementById("stat-total").textContent = meta.total_n ?? "—";

  const sip = meta.group_counts?.["SIP"] ?? "—";
  const nonSip = meta.group_counts?.["Not SIP"] ?? "—";
  document.getElementById("stat-sip").textContent = sip;
  document.getElementById("stat-non-sip").textContent = nonSip;
  document.getElementById("stat-sig").textContent = `${meta.n_significant} / ${meta.n_variables}`;

  // Remove skeleton
  document.querySelectorAll(".stat-card").forEach(el => el.classList.remove("skeleton"));

  // Meta line
  const ts = meta.generated_at
    ? new Date(meta.generated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })
    : "—";
  document.getElementById("meta-line").textContent =
    `Last analysed: ${ts} UTC · N = ${meta.total_n} patients`;
  document.getElementById("footer-ts").textContent = ts;
}

// ─────────────────────────────────────────────────────────────────
// Render Table One
// ─────────────────────────────────────────────────────────────────
function buildTable(data, meta) {
  const groupKeys = Object.entries(meta.group_labels ?? {})
    .filter(([, v]) => v)
    .map(([k, v]) => ({ key: k, label: v }));

  // Build thead
  const thead = document.getElementById("thead");
  const thRow = document.createElement("tr");
  ["Variable", "Level", "Overall", ...groupKeys.map(g => g.label), "p-value", "Test", "SMD", "OR (95% CI)"]
    .forEach((h, i) => {
      const th = document.createElement("th");
      th.textContent = h;
      if (i === 0) th.style.minWidth = "180px";
      thRow.appendChild(th);
    });
  thead.appendChild(thRow);

  // Build rows
  const tbody = document.getElementById("tbody");
  data.forEach(va => {
    const isCat = va.var_type === "categorical";
    const isSig = va.significant;

    if (isCat && typeof va.stats_overall === "object" && va.stats_overall !== null) {
      // One row per level
      const levels = Object.keys(va.stats_overall).sort();
      levels.forEach((level, i) => {
        const tr = buildRow({
          variable: i === 0 ? va.label : "",
          level,
          overall: va.stats_overall[level] ?? "—",
          groupVals: groupKeys.map(g => {
            const gd = va.stats_groups?.[g.label];
            return (typeof gd === "object" && gd !== null) ? (gd[level] ?? "0 (0.0%)") : "—";
          }),
          pval: i === 0 ? va.p_value_fmt : "",
          test: i === 0 ? va.test_name : "",
          smd: i === 0 ? fmtSMD(va.extra_stats?.smd) : "",
          or: i === 0 ? fmtOR(va.extra_stats?.or) : "",
          varType: i === 0 ? va.var_type : "",
          isSig,
          isFirstRow: i === 0,
          isLevel: true,
        });
        tbody.appendChild(tr);
      });
    } else {
      // Single row
      const groupVals = groupKeys.map(g => {
        const v = va.stats_groups?.[g.label];
        return typeof v === "string" ? v : "—";
      });
      const tr = buildRow({
        variable: va.label,
        level: "",
        overall: typeof va.stats_overall === "string" ? va.stats_overall : "—",
        groupVals,
        pval: va.p_value_fmt,
        test: va.test_name,
        smd: fmtSMD(va.extra_stats?.smd),
        or: fmtOR(va.extra_stats?.or),
        varType: va.var_type,
        isSig,
        isFirstRow: true,
        isLevel: false,
      });
      tbody.appendChild(tr);
    }
  });

  document.getElementById("loading-state").remove();
  document.getElementById("tableone").hidden = false;
}

function buildRow({ variable, level, overall, groupVals, pval, test, smd, or, varType, isSig, isFirstRow, isLevel }) {
  const tr = document.createElement("tr");
  tr.dataset.varType = varType;
  tr.dataset.sig = isSig ? "sig" : "ns";
  tr.dataset.label = (variable + " " + level).toLowerCase();
  if (isSig && isFirstRow) tr.classList.add("sig-row");

  const cells = [
    { content: variable, cls: "col-var" },
    { content: level, cls: isLevel ? "col-level" : "" },
    { content: overall, cls: "col-mono" },
    ...groupVals.map(v => ({ content: v, cls: "col-mono" })),
    { content: pval, cls: "pval-cell" },
    { content: test, cls: "" },
    { content: smd, cls: "col-mono" },
    { content: or, cls: "col-mono" },
  ];

  cells.forEach(({ content, cls }) => {
    const td = document.createElement("td");
    if (cls === "pval-cell") {
      td.innerHTML = formatPvalCell(pval);
    } else if (cls === "col-var" && isFirstRow && varType) {
      td.innerHTML = `${escapeHtml(content)} <span class="type-badge ${typeBadgeCls(varType)}">${typeBadgeText(varType)}</span>`;
    } else {
      td.textContent = content ?? "";
    }
    if (cls && cls !== "pval-cell" && cls !== "col-var") td.className = cls;
    tr.appendChild(td);
  });

  return tr;
}

function formatPvalCell(pval) {
  if (!pval || pval === "—") return `<span class="pval-dash">—</span>`;
  if (pval === "<0.001" || (parseFloat(pval) < 0.05 && pval !== "")) {
    return `<span class="pval-sig">${escapeHtml(pval)} ✦</span>`;
  }
  return `<span class="pval-ns">${escapeHtml(pval)}</span>`;
}

function typeBadgeCls(vt) {
  if (vt === "categorical") return "cat";
  if (vt === "continuous_normal") return "norm";
  if (vt === "continuous_non_normal") return "nonorm";
  return "";
}

function typeBadgeText(vt) {
  if (vt === "categorical") return "CAT";
  if (vt === "continuous_normal") return "NORM";
  if (vt === "continuous_non_normal") return "NON-NORM";
  return "?";
}

function fmtSMD(smd) {
  if (smd == null) return "—";
  return parseFloat(smd).toFixed(3);
}

function fmtOR(or) {
  if (!or || typeof or !== "object") return "—";
  const lo = or.ci_lo != null ? or.ci_lo : "?";
  const hi = or.ci_hi != null ? or.ci_hi : "?";
  return `${or.or} (${lo}–${hi})`;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ─────────────────────────────────────────────────────────────────
// Key Findings
// ─────────────────────────────────────────────────────────────────
function renderFindings(data, meta) {
  const grid = document.getElementById("findings-grid");
  const sigVars = data.filter(v => v.significant);

  if (sigVars.length === 0) {
    grid.innerHTML = `<p class="no-findings">No significant differences found (p &lt; 0.05) in this analysis.</p>`;
    return;
  }

  // Sort by p-value ascending
  sigVars.sort((a, b) => (a.p_value ?? 1) - (b.p_value ?? 1));

  sigVars.forEach((va, idx) => {
    const card = document.createElement("div");
    card.className = "finding-card";
    card.style.animationDelay = `${idx * 60}ms`;

    const groupLines = Object.entries(va.stats_groups ?? {})
      .map(([grp, val]) => {
        const display = typeof val === "object" ? Object.values(val).slice(0, 2).join(", ") : val;
        return `<span>${escapeHtml(grp)}: ${escapeHtml(display)}</span>`;
      })
      .join("");

    card.innerHTML = `
      <div class="finding-var">${escapeHtml(va.var_type?.replace(/_/g, " ") ?? "")}</div>
      <div class="finding-label">${escapeHtml(va.label)}</div>
      <div class="finding-stats">${groupLines}</div>
      <div class="finding-pval">p = ${escapeHtml(va.p_value_fmt)} · ${escapeHtml(va.test_name)}</div>
    `;

    grid.appendChild(card);
  });
}

// ─────────────────────────────────────────────────────────────────
// Filters
// ─────────────────────────────────────────────────────────────────
function applyFilters() {
  const typeVal = document.getElementById("filter-type").value;
  const sigVal  = document.getElementById("filter-sig").value;
  const search  = document.getElementById("search-var").value.toLowerCase().trim();

  const rows = document.querySelectorAll("#tbody tr");
  let visibleCount = 0;

  rows.forEach(tr => {
    const rowType = tr.dataset.varType || "";
    const rowSig  = tr.dataset.sig || "";
    const rowLabel = tr.dataset.label || "";

    const typeOk = typeVal === "all" || rowType === typeVal || rowType === "";
    const sigOk  = sigVal === "all" || rowSig === sigVal || rowSig === "";
    const searchOk = !search || rowLabel.includes(search);

    const visible = typeOk && sigOk && searchOk;
    tr.style.display = visible ? "" : "none";
    if (visible) visibleCount++;
  });

  // Show empty state if no results
  const existing = document.querySelector(".empty-state");
  if (visibleCount === 0) {
    if (!existing) {
      const td = document.createElement("tr");
      td.className = "empty-state";
      td.innerHTML = `<td colspan="20" class="empty-state">No variables match the current filters.</td>`;
      document.getElementById("tbody").appendChild(td);
    }
  } else {
    existing?.remove();
  }
}

// ─────────────────────────────────────────────────────────────────
// CSV Export
// ─────────────────────────────────────────────────────────────────
function exportCSV(data, meta) {
  const groupKeys = Object.values(meta.group_labels ?? {}).filter(Boolean);
  const headers = ["Variable", "Level", "Overall", ...groupKeys, "p_value", "test_name", "SMD", "OR", "CI_lo", "CI_hi"];

  const rows = [headers.join(",")];

  data.forEach(va => {
    const isCat = va.var_type === "categorical" && typeof va.stats_overall === "object";
    if (isCat) {
      Object.keys(va.stats_overall ?? {}).sort().forEach(level => {
        const groupVals = groupKeys.map(g => {
          const gd = va.stats_groups?.[g];
          return typeof gd === "object" ? (gd?.[level] ?? "") : "";
        });
        rows.push([
          `"${va.label}"`, `"${level}"`,
          `"${va.stats_overall[level] ?? ""}"`,
          ...groupVals.map(v => `"${v}"`),
          "", "", "", "", "",
        ].join(","));
      });
    } else {
      const groupVals = groupKeys.map(g => va.stats_groups?.[g] ?? "");
      const or = va.extra_stats?.or ?? {};
      rows.push([
        `"${va.label}"`, "",
        `"${va.stats_overall ?? ""}"`,
        ...groupVals.map(v => `"${v}"`),
        va.p_value_fmt ?? "",
        `"${va.test_name ?? ""}"`,
        va.extra_stats?.smd != null ? parseFloat(va.extra_stats.smd).toFixed(3) : "",
        or.or ?? "", or.ci_lo ?? "", or.ci_hi ?? "",
      ].join(","));
    }
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sip_tableone.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────
// Reveal animation (Intersection Observer)
// ─────────────────────────────────────────────────────────────────
function initReveal() {
  const obs = new IntersectionObserver(
    entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add("visible"); }),
    { threshold: 0.15 }
  );
  document.querySelectorAll(".reveal").forEach(el => obs.observe(el));
}

// ─────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────
async function main() {
  try {
    const [data, meta] = await Promise.all([
      fetchJSON(`${DATA_BASE}/tableone.json`),
      fetchJSON(`${DATA_BASE}/metadata.json`),
    ]);

    renderMeta(meta);
    buildTable(data, meta);
    renderFindings(data, meta);

    // Wire up filters
    ["filter-type", "filter-sig", "search-var"].forEach(id => {
      document.getElementById(id).addEventListener("input", applyFilters);
    });

    // Export
    document.getElementById("btn-export-csv").addEventListener("click", () => exportCSV(data, meta));

    initReveal();
  } catch (err) {
    console.error("Failed to load analysis data:", err);

    document.getElementById("loading-state").innerHTML = `
      <div style="color:var(--danger);text-align:center;padding:3rem">
        <p style="font-size:1.5rem;margin-bottom:0.5rem">⚠️ Data not found</p>
        <p style="font-size:0.9rem;color:var(--text-muted)">
          Run the GitHub Actions workflow first to generate analysis data.<br/>
          Go to <strong>Actions → SIP Statistical Analysis → Run workflow</strong>
        </p>
      </div>
    `;

    document.querySelectorAll(".stat-card").forEach(el => {
      el.classList.remove("skeleton");
    });
    document.getElementById("meta-line").textContent = "No data available — trigger GitHub Actions to analyse.";
  }
}

document.addEventListener("DOMContentLoaded", main);

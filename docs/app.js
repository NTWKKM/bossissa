// app.js - Bossissa SIP Analysis Frontend
document.addEventListener("DOMContentLoaded", async () => {
  // Elements
  const stats = {
    total: document.getElementById("stat-total"),
    sip: document.getElementById("stat-sip"),
    nonSip: document.getElementById("stat-non-sip"),
    sig: document.getElementById("stat-sig")
  };
  const footerTs = document.getElementById("footer-ts");
  const thead = document.getElementById("thead");
  const tbody = document.getElementById("tbody");
  const table = document.getElementById("tableone");
  const loadingState = document.getElementById("loading-state");
  const findingsGrid = document.getElementById("findings-grid");

  const filterType = document.getElementById("filter-type");
  const filterSig = document.getElementById("filter-sig");
  const searchVar = document.getElementById("search-var");
  const btnExport = document.getElementById("btn-export-csv");

  // Tab Elements
  const tabTableOne = document.getElementById("tab-tableone");
  const tabCharts = document.getElementById("tab-charts");
  const tabStat = document.getElementById("tab-stat");
  const tabMulti = document.getElementById("tab-multi");
  const pageTableOne = document.getElementById("page-tableone");
  const pageCharts = document.getElementById("page-charts");
  const pageStat = document.getElementById("page-stat");
  const pageMulti = document.getElementById("page-multi");
  const chartsGrid = document.getElementById("charts-grid");
  const chartsLoading = document.getElementById("charts-loading");

  // Theme Toggle Logic
  const themeToggle = document.getElementById("theme-toggle");
  const themeIcon = document.getElementById("theme-icon");
  
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("bossissa-theme", theme);
    themeIcon.textContent = theme === "dark" ? "☀️" : "🌓";
  }

  const savedTheme = localStorage.getItem("bossissa-theme");
  if (savedTheme) {
    applyTheme(savedTheme);
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      applyTheme(current === "light" ? "dark" : "light");
    });
  }

  let tableData = [];
  let metaData = null;
  let chartsData = [];
  let statData = null;

  // 1. Fetch Data (core: metadata + tableone only; charts + stat_freq lazy-loaded)
  try {
    const [metaRes, tableRes] = await Promise.all([
      fetch("data/metadata.json"),
      fetch("data/tableone.json")
    ]);

    if (!metaRes.ok || !tableRes.ok) throw new Error("Data files not found");

    metaData = await metaRes.json();
    tableData = await tableRes.json();

    populateHero();
    renderTable();
    renderFindings();

    // Hide loading, show table
    loadingState.style.display = "none";
    table.hidden = false;

  } catch (err) {
    console.error(err);
    loadingState.innerHTML = `<p style="color:var(--accent-red)">Error loading analysis data. Ensure the GitHub Action has run.</p>`;
  }

  // 2. Core Rendering
  function populateHero() {
    if (!metaData) return;
    stats.total.textContent = metaData.total_n;
    stats.sip.textContent = metaData.group_counts["SIP"] || 0;
    stats.nonSip.textContent = metaData.group_counts["Not SIP"] || 0;
    stats.sig.textContent = metaData.n_significant;

    document.querySelectorAll(".skeleton").forEach(el => el.classList.remove("skeleton"));
    document.getElementById("meta-line").innerHTML = `
      Data updated: <span class="ts">${new Date(metaData.generated_at).toLocaleString()}</span>
    `;
    footerTs.textContent = `Last run: ${new Date(metaData.generated_at).toLocaleString()}`;
  }

  function renderTable() {
    if (!tableData.length || !metaData) return;

    const term = searchVar.value.toLowerCase();
    const type = filterType.value;
    const sig = filterSig.value;

    const filtered = tableData.filter(r => {
      if (term && !r.name.toLowerCase().includes(term) && !(r.label && r.label.toLowerCase().includes(term))) return false;
      if (type !== "all" && r.var_type !== type) return false;
      if (sig === "sig" && (r.p_value === null || r.p_value >= 0.05)) return false;
      if (sig === "ns" && r.p_value !== null && r.p_value < 0.05) return false;
      return true;
    });

    const groupKeys = Object.keys(metaData.group_counts || {});
    const g0Name = groupKeys.length > 0 ? groupKeys[0] : "Group 0";
    const g1Name = groupKeys.length > 1 ? groupKeys[1] : "Group 1";
    const g0N = metaData.group_counts[g0Name] || 0;
    const g1N = metaData.group_counts[g1Name] || 0;

    thead.innerHTML = `
      <tr>
        <th>Variable</th>
        <th>Total (N=${metaData.total_n})</th>
        <th>${g0Name} (n=${g0N})</th>
        <th>${g1Name} (n=${g1N})</th>
        <th>p-value</th>
        <th>Effect Size</th>
      </tr>
    `;

    tbody.innerHTML = filtered.map(r => {
      let pClass = r.p_value !== null && r.p_value < 0.05 ? 'style="color:var(--accent-green);font-weight:600"' : '';
      let effectHtml = "-";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null) {
          const orData = r.extra_stats.or;
          const ciLo = (orData.ci_lo !== null && orData.ci_lo !== undefined) ? orData.ci_lo.toFixed(2) : '?';
          const ciHi = (orData.ci_hi !== null && orData.ci_hi !== undefined) ? orData.ci_hi.toFixed(2) : '?';
          effectHtml = `OR: ${orData.or.toFixed(2)} [${ciLo}–${ciHi}]`;
        } else if (r.extra_stats.smd !== undefined && r.extra_stats.smd !== null) {
          effectHtml = `SMD: ${r.extra_stats.smd.toFixed(3)}`;
        }
      }

      let totalStr = "";
      let g0Str = "";
      let g1Str = "";

      if (r.var_type === "categorical") {
        const levels = Object.keys(r.stats_overall || {});
        totalStr = levels.map(l => `<div style="margin-bottom:2px"><b>${l}:</b> ${r.stats_overall[l]}</div>`).join("");
        g0Str = levels.map(l => `<div style="margin-bottom:2px">${r.stats_groups[g0Name]?.[l] || "-"}</div>`).join("");
        g1Str = levels.map(l => `<div style="margin-bottom:2px">${r.stats_groups[g1Name]?.[l] || "-"}</div>`).join("");
      } else {
        totalStr = r.stats_overall || "-";
        g0Str = r.stats_groups[g0Name] || "-";
        g1Str = r.stats_groups[g1Name] || "-";
      }

      return `
        <tr>
          <td class="col-var">
            ${r.label || r.name}
            <div style="font-size:0.7rem;color:var(--text-muted);font-weight:400">${r.var_type.replaceAll('_', ' ')}</div>
          </td>
          <td>${totalStr}</td>
          <td>${g0Str}</td>
          <td>${g1Str}</td>
          <td ${pClass}>${r.p_value_fmt}</td>
          <td style="font-size:0.8rem;color:var(--text-secondary)">${effectHtml}</td>
        </tr>
      `;
    }).join("");
  }

  function renderFindings() {
    const sigVars = tableData.filter(r => r.p_value !== null && r.p_value < 0.05);
    
    if (sigVars.length === 0) {
      findingsGrid.innerHTML = `<div style="grid-column:1/-1;color:var(--text-muted)">No statistically significant findings (p < 0.05) found in this dataset.</div>`;
      return;
    }

    findingsGrid.innerHTML = sigVars.map(r => {
      let effectHtml = "";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null) effectHtml = `OR: ${r.extra_stats.or.or.toFixed(2)}`;
        else if (r.extra_stats.smd !== undefined && r.extra_stats.smd !== null) effectHtml = `SMD: ${r.extra_stats.smd.toFixed(2)}`;
      }

      let g0Str = "";
      let g1Str = "";
      const groupKeys = Object.keys(metaData.group_counts || {});
      const g0Name = groupKeys.length > 0 ? groupKeys[0] : "Group 0";
      const g1Name = groupKeys.length > 1 ? groupKeys[1] : "Group 1";

      if (r.var_type === "categorical") {
        const levels = Object.keys(r.stats_overall || {});
        g0Str = levels.map(l => `${l}: ${r.stats_groups[g0Name]?.[l] || "-"}`).join(", ");
        g1Str = levels.map(l => `${l}: ${r.stats_groups[g1Name]?.[l] || "-"}`).join(", ");
      } else {
        g0Str = r.stats_groups[g0Name] || "-";
        g1Str = r.stats_groups[g1Name] || "-";
      }

      return `
        <div class="finding-card reveal">
          <div class="finding-header">
            <span class="finding-title">${r.label || r.name}</span>
            <span class="finding-pval">p = ${r.p_value_fmt}</span>
          </div>
          <div class="finding-body">
            <div><strong>${g0Name}:</strong> ${g0Str}</div>
            <div><strong>${g1Name}:</strong> ${g1Str}</div>
            ${effectHtml ? `<div style="margin-top:0.5rem;font-size:0.85rem;color:var(--text-muted)">${effectHtml}</div>` : ''}
          </div>
        </div>
      `;
    }).join("");
  }

  // 3. Tab Navigation (with lazy-loading for charts + stat_freq + multivariate)
  let chartsLoaded = false;
  let statLoaded = false;
  let multiLoaded = false;

  function switchTab(tabId) {
    [tabTableOne, tabCharts, tabStat, tabMulti].forEach(el => {
      if (el) {
        el.classList.remove("active");
        el.setAttribute("aria-selected", "false");
      }
    });
    [pageTableOne, pageCharts, pageStat, pageMulti].forEach(el => {
      if (el) el.hidden = true;
    });

    if (tabId === "tableone") {
      tabTableOne.classList.add("active");
      tabTableOne.setAttribute("aria-selected", "true");
      pageTableOne.hidden = false;
    } else if (tabId === "charts") {
      tabCharts.classList.add("active");
      tabCharts.setAttribute("aria-selected", "true");
      pageCharts.hidden = false;
      
      if (!chartsLoaded) {
        loadCharts();
      } else {
        setTimeout(() => {
          if (window.Plotly) {
            document.querySelectorAll('.js-plotly-plot').forEach(el => Plotly.Plots.resize(el));
          }
        }, 50);
      }
    } else if (tabId === "stat") {
      if (tabStat) {
        tabStat.classList.add("active");
        tabStat.setAttribute("aria-selected", "true");
      }
      if (pageStat) pageStat.hidden = false;
      
      if (!statLoaded) {
        loadStatFreq();
      }
    } else if (tabId === "multi") {
      if (tabMulti) {
        tabMulti.classList.add("active");
        tabMulti.setAttribute("aria-selected", "true");
      }
      if (pageMulti) pageMulti.hidden = false;
      
      if (!multiLoaded) {
        loadMultivariate();
      }
    }
  }

  async function loadCharts() {
    try {
      const res = await fetch("data/charts.json");
      if (!res.ok) throw new Error("charts.json not found");
      chartsData = await res.json();
      chartsLoading.style.display = "none";
      renderCharts();
      chartsLoaded = true;
    } catch (err) {
      chartsLoading.innerHTML = `<p style="color:var(--accent-red)">Error loading chart data.</p>`;
    }
  }

  async function loadStatFreq() {
    try {
      const res = await fetch("data/stat_freq.json");
      if (!res.ok) throw new Error("stat_freq.json not found");
      statData = await res.json();
      renderStatTabs();
      statLoaded = true;
    } catch (err) {
      document.getElementById("stat-loading-state").innerHTML = `<p style="color:var(--accent-red)">Error loading stat data.</p>`;
    }
  }

  async function loadMultivariate() {
    try {
      const res = await fetch("data/multivariate.json");
      if (!res.ok) throw new Error("multivariate.json not found");
      const multiData = await res.json();
      renderMultivariate(multiData);
      multiLoaded = true;
    } catch (err) {
      document.getElementById("multi-loading-state").innerHTML = `<p style="color:var(--accent-red)">Error loading multivariate data. Ensure the GitHub Action has run.</p>`;
    }
  }

  function renderMultivariate(data) {
    document.getElementById("multi-loading-state").style.display = "none";
    document.getElementById("multi-content-area").hidden = false;

    // Summary stats
    document.getElementById("multi-n-features").textContent = `${data.n_features_selected}/${data.n_features_total}`;
    document.getElementById("multi-lasso-c").textContent = data.lasso_C;
    document.getElementById("multi-firth-sig").textContent = data.firth.variables.filter(v => v.significant).length;
    document.getElementById("multi-std-sig").textContent = data.standard.variables.filter(v => v.significant && v.name !== "Intercept").length;

    // Firth meta
    document.getElementById("multi-firth-meta").textContent = `Method: ${data.firth.method}. ${data.firth.n_iterations} iterations.`;

    // Standard meta
    document.getElementById("multi-std-meta").textContent = `Method: ${data.standard.method}. Pseudo R² = ${data.standard.pseudo_r2}. Log-likelihood = ${data.standard.log_likelihood}.`;

    // Render both tables
    renderMultiTable("firth", data.firth.variables);
    renderMultiTable("std", data.standard.variables);

    // Interpretation cards
    renderMultiInterpretation(data);
  }

  function renderMultiTable(idPrefix, variables) {
    const thead = document.getElementById(`thead-${idPrefix}`);
    const tbody = document.getElementById(`tbody-${idPrefix}`);
    if (!thead || !tbody) return;

    thead.innerHTML = `<tr>
      <th>Predictor</th>
      <th>Coef (β)</th>
      <th>SE</th>
      <th>OR</th>
      <th>95% CI</th>
      <th>p-value</th>
    </tr>`;

    tbody.innerHTML = variables.map(v => {
      const pClass = v.significant ? 'style="color:var(--accent-green);font-weight:600"' : '';
      const ciStr = `[${v.ci_lo}–${v.ci_hi}]`;
      const orDisplay = v.or > 1 ? `<span style="color:var(--accent-red)">${v.or}</span>` : v.or < 1 ? `<span style="color:var(--accent-green)">${v.or}</span>` : v.or;
      return `<tr>
        <td class="col-var">${v.name}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${v.coef}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${v.se}</td>
        <td style="font-family:var(--font-mono);font-weight:600">${orDisplay}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${ciStr}</td>
        <td ${pClass} style="font-family:var(--font-mono)">${v.p_value}</td>
      </tr>`;
    }).join("");
  }

  function renderMultiInterpretation(data) {
    const grid = document.getElementById("multi-interp");
    if (!grid) return;

    const firthSig = data.firth.variables.filter(v => v.significant);
    const stdSig = data.standard.variables.filter(v => v.significant && v.name !== "Intercept");
    const firthNames = new Set(firthSig.map(v => v.name));
    const stdNames = new Set(stdSig.map(v => v.name));
    const agree = [...firthNames].filter(n => stdNames.has(n));
    const intercept = data.standard.variables.find(v => v.name === "Intercept");

    const bullets = [];

    // 1. LASSO
    bullets.push(`<strong>🎯 LASSO Feature Selection</strong> — From ${data.n_features_total} candidate features, LASSO (C=${data.lasso_C}) selected <strong>${data.n_features_selected}</strong> independent predictors by minimizing AIC. This sparse model handles multicollinearity — redundant variables are dropped.`);

    // 2. Agreement
    bullets.push(`<strong>🤝 Firth vs Standard Agreement</strong> — Both methods agree on <strong>${agree.length} significant predictor${agree.length !== 1 ? 's' : ''}</strong>: ${agree.join(", ") || "none"}. Firth penalized likelihood provides more conservative profile-likelihood CIs — preferred reference when separation is a concern.`);

    // 3. Significant predictors
    if (firthSig.length > 0) {
      const items = firthSig.map(v => {
        const direction = v.or < 1 ? "protective" : "risk";
        const strength = Math.abs(v.or - 1) < 0.2 ? "weak" : Math.abs(v.or - 1) < 0.5 ? "moderate" : "strong";
        return `<strong>${v.name}</strong>: OR = ${v.or} [${v.ci_lo}–${v.ci_hi}] (${direction}, ${strength}), p = ${v.p_value}`;
      }).join(" · ");
      bullets.push(`<strong>🔍 Significant Predictors (Firth)</strong> — ${items}`);
    }

    // 4. Baseline
    if (intercept) {
      bullets.push(`<strong>📏 Baseline (Intercept)</strong> — OR = <strong>${intercept.or}</strong> [${intercept.ci_lo}–${intercept.ci_hi}], p = ${intercept.p_value}. Baseline SIP odds when all predictors are at reference level: <strong>บัตรทอง</strong> (insurance), <strong>no delusion</strong>, <strong>complete DSM-5 functional impairment data</strong>. At ~1.4:1, this reflects the high SIP prevalence in this population. The intercept is a statistical reference point, not a clinical predictor.`);
    }

    // 5. Model fit
    bullets.push(`<strong>📐 Model Fit</strong> — Pseudo R² = ${data.standard.pseudo_r2}. The selected features explain a small portion of variance in SIP diagnosis. SIP determination is multifactorial — unmeasured confounders (substance dose, duration, genetics, social factors) likely play major roles.`);

    grid.innerHTML = `
      <div class="interp-box reveal">
        <h3 style="margin-bottom:1rem;font-size:1.1rem">Key Findings</h3>
        <ul style="list-style:none;padding:0;display:flex;flex-direction:column;gap:0.85rem;line-height:1.7">
          ${bullets.map(b => `<li>${b}</li>`).join("")}
        </ul>
      </div>
    `;
    observeReveal(grid);
  }

  tabTableOne.addEventListener("click", () => switchTab("tableone"));
  tabCharts.addEventListener("click", () => switchTab("charts"));
  if (tabStat) tabStat.addEventListener("click", () => switchTab("stat"));
  if (tabMulti) tabMulti.addEventListener("click", () => switchTab("multi"));

  // 4. Plotly Charts Rendering (with per-chart error isolation)
  function renderCharts() {
    if (!window.Plotly) {
      console.warn("Plotly not loaded yet, retrying in 200ms...");
      setTimeout(renderCharts, 200);
      return;
    }

    chartsGrid.innerHTML = "";
    chartsData.forEach((spec, i) => {
      const containerId = `chart-${spec.id || i}`;
      const div = document.createElement("div");
      div.className = "chart-container reveal";
      div.id = containerId;
      chartsGrid.appendChild(div);

      try {
        const layout = Object.assign({}, spec.layout);
        const config = { responsive: true, displayModeBar: false };
        Plotly.newPlot(containerId, spec.data, layout, config);
      } catch (err) {
        console.error(`Chart ${spec.id || i} failed:`, err);
        div.innerHTML = `<p style="color:var(--accent-red);padding:2rem;text-align:center">Chart "${spec.title || spec.id}" failed to render.</p>`;
      }
    });
    observeReveal(chartsGrid);
  }

  // 5. Interactivity
  let debounceTimer;
  [filterType, filterSig].forEach(el => {
    el.addEventListener("change", renderTable);
  });
  searchVar.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(renderTable, 200);
  });

  btnExport.addEventListener("click", () => {
    if (!tableData.length) return;
    const groupKeys = Object.keys(metaData.group_counts || {});
    const g0Name = groupKeys.length > 0 ? groupKeys[0] : "Group 0";
    const g1Name = groupKeys.length > 1 ? groupKeys[1] : "Group 1";

    const csvRows = [];
    csvRows.push(["Variable", "Type", "Total", g0Name, g1Name, "p-value", "Effect_Type", "Effect_Size", "Effect_CI_Low", "Effect_CI_High"].join(","));
    
    tableData.forEach(r => {
      let ciLo = "", ciHi = "", effectType = "", effectSize = "";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null) {
          effectType = "OR";
          effectSize = r.extra_stats.or.or;
          ciLo = r.extra_stats.or.ci_lo;
          ciHi = r.extra_stats.or.ci_hi;
        } else if (r.extra_stats.smd !== undefined && r.extra_stats.smd !== null) {
          effectType = "SMD";
          effectSize = r.extra_stats.smd;
        }
      }

      let totalStr = r.stats_overall;
      let g0Str = r.stats_groups[g0Name];
      let g1Str = r.stats_groups[g1Name];

      if (r.var_type === "categorical") {
        totalStr = JSON.stringify(totalStr);
        g0Str = JSON.stringify(g0Str);
        g1Str = JSON.stringify(g1Str);
      }

      const row = [
        `"${r.name}"`,
        r.var_type,
        `"${totalStr}"`,
        `"${g0Str || ''}"`,
        `"${g1Str || ''}"`,
        r.p_value,
        effectType,
        effectSize,
        ciLo,
        ciHi
      ];
      csvRows.push(row.join(","));
    });

    const blob = new Blob([csvRows.join("\n")], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sip_table_one_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  });

  // Reveal animation observer
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = 1;
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });

  function observeReveal(root = document) {
    root.querySelectorAll('.reveal').forEach(el => observer.observe(el));
  }
  observeReveal();

  // 6. Frequency Stats Rendering
  function renderStatTabs() {
    if (!statData) return;
    
    const loadingState = document.getElementById("stat-loading-state");
    if (loadingState) loadingState.style.display = "none";
    
    const statContent = document.getElementById("stat-content-area");
    if (statContent) statContent.hidden = false;

    renderStatTable("inclusion", statData.inclusion, statData.total_n);
    renderStatTable("hx", statData.hx_psych, statData.total_n);
    renderStatTable("sip", statData.sip_all, statData.total_n);
  }

  function renderStatTable(idPrefix, groupData, totalN) {
    const thead = document.getElementById(`thead-${idPrefix}`);
    const tbody = document.getElementById(`tbody-${idPrefix}`);
    
    if (!thead || !tbody || !groupData || !groupData.results) return;

    const groupKeys = Object.keys(groupData.group_labels).sort((a,b) => parseInt(a) - parseInt(b));
    
    let theadHtml = `<tr>
      <th>Variable</th>
      <th>Total (N=${totalN})</th>`;
    
    groupKeys.forEach(k => {
      const label = groupData.group_labels[k];
      const count = groupData.group_counts[label] || 0;
      theadHtml += `<th>${label} (n=${count})</th>`;
    });
    
    theadHtml += `<th>p-value</th></tr>`;
    thead.innerHTML = theadHtml;

    const rows = groupData.results.map(r => {
      let pClass = r.p_value !== null && r.p_value < 0.05 ? 'style="color:var(--accent-green);font-weight:600"' : '';
      
      let totalStr = "";
      let groupStrs = groupKeys.map(() => "");

      if (r.var_type === "categorical") {
        const levels = Object.keys(r.stats_overall || {});
        totalStr = levels.map(l => `<div style="margin-bottom:2px"><b>${l}:</b> ${r.stats_overall[l]}</div>`).join("");
        
        groupStrs = groupKeys.map(k => {
          const label = groupData.group_labels[k];
          return levels.map(l => `<div style="margin-bottom:2px">${r.stats_groups[label]?.[l] || "-"}</div>`).join("");
        });
      } else {
        totalStr = r.stats_overall || "-";
        groupStrs = groupKeys.map(k => {
          const label = groupData.group_labels[k];
          return r.stats_groups[label] || "-";
        });
      }

      let rowHtml = `
        <tr>
          <td class="col-var">
            ${r.label || r.name}
            <div style="font-size:0.7rem;color:var(--text-muted);font-weight:400">${r.var_type.replaceAll('_', ' ')}</div>
          </td>
          <td>${totalStr}</td>
      `;

      groupStrs.forEach(gStr => {
        rowHtml += `<td>${gStr}</td>`;
      });

      rowHtml += `<td ${pClass}>${r.p_value_fmt}</td></tr>`;
      return rowHtml;
    });

    tbody.innerHTML = rows.join("");
  }
});

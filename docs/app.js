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
  const filterCorrection = document.getElementById("filter-correction");
  const searchVar = document.getElementById("search-var");
  const btnExport = document.getElementById("btn-export-csv");
  const btnExportLatex = document.getElementById("btn-export-latex");

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
  
  // Observe static reveal elements on page load
  observeReveal(document);

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
    const correction = filterCorrection ? filterCorrection.value : "none";

    const filtered = tableData.filter(r => {
      if (term && !r.name.toLowerCase().includes(term) && !(r.label && r.label.toLowerCase().includes(term))) return false;
      if (type !== "all" && r.var_type !== type) return false;
      
      let pVal = r.p_value;
      if (correction === "bonferroni") pVal = r.p_value_bonferroni;
      else if (correction === "fdr_bh") pVal = r.p_value_bh;

      if (sig === "sig" && (pVal === null || pVal >= 0.05)) return false;
      if (sig === "ns" && pVal !== null && pVal < 0.05) return false;
      return true;
    });

    const groupKeys = Object.keys(metaData.group_counts || {});
    const g0Name = groupKeys.length > 0 ? groupKeys[0] : "Group 0";
    const g1Name = groupKeys.length > 1 ? groupKeys[1] : "Group 1";
    const g0N = metaData.group_counts[g0Name] || 0;
    const g1N = metaData.group_counts[g1Name] || 0;

    let pLabel = "p-value";
    if (correction === "bonferroni") pLabel = "p-value (Bonf.)";
    else if (correction === "fdr_bh") pLabel = "p-value (BH-FDR)";

    thead.innerHTML = `
      <tr>
        <th>Variable</th>
        <th>Total (N=${metaData.total_n})</th>
        <th>Missing</th>
        <th>${g0Name} (n=${g0N})</th>
        <th>${g1Name} (n=${g1N})</th>
        <th>${pLabel}</th>
        <th>Test</th>
        <th>Effect Size</th>
      </tr>
    `;

    tbody.innerHTML = filtered.map(r => {
      let pVal = r.p_value;
      let pValFmt = r.p_value_fmt;
      if (correction === "bonferroni") {
        pVal = r.p_value_bonferroni;
        pValFmt = r.p_value_bonferroni_fmt;
      } else if (correction === "fdr_bh") {
        pVal = r.p_value_bh;
        pValFmt = r.p_value_bh_fmt;
      }

      let pClass = pVal !== null && pVal < 0.05 ? 'style="color:var(--accent-green);font-weight:600"' : '';
      let effectHtml = "-";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null && Object.keys(r.extra_stats.or).length > 0) {
          const orData = r.extra_stats.or;
          const ciLo = (orData.ci_lo !== null && orData.ci_lo !== undefined) ? orData.ci_lo.toFixed(2) : '?';
          const ciHi = (orData.ci_hi !== null && orData.ci_hi !== undefined) ? orData.ci_hi.toFixed(2) : '?';
          effectHtml = `OR: ${orData.or.toFixed(2)} [${ciLo}–${ciHi}]`;
        } else if (r.extra_stats.smd !== undefined && r.extra_stats.smd !== null) {
          effectHtml = `SMD: ${r.extra_stats.smd.toFixed(3)}`;
        }
      }

      let totalStr = "";
      let missStr = "";
      let g0Str = "";
      let g1Str = "";

      const missColor = r.n_missing > 0 ? 'var(--accent-orange)' : 'var(--text-muted)';
      const missText = `<span style="color:${missColor}">${r.n_missing} (${r.pct_missing}%)</span>`;

      if (r.var_type === "categorical") {
        const levels = Object.keys(r.stats_overall || {});
        totalStr = levels.map(l => `<div style="margin-bottom:2px"><b>${l}:</b> ${r.stats_overall[l]}</div>`).join("");
        missStr = `<div style="margin-bottom:2px">${missText}</div>` + levels.slice(1).map(l => `<div style="margin-bottom:2px"></div>`).join("");
        g0Str = levels.map(l => `<div style="margin-bottom:2px">${r.stats_groups[g0Name]?.[l] || "-"}</div>`).join("");
        g1Str = levels.map(l => `<div style="margin-bottom:2px">${r.stats_groups[g1Name]?.[l] || "-"}</div>`).join("");
      } else {
        totalStr = r.stats_overall || "-";
        missStr = missText;
        g0Str = r.stats_groups[g0Name] || "-";
        g1Str = r.stats_groups[g1Name] || "-";
      }

      const testStyle = (r.test_name || "").includes("⚠")
        ? 'style="color:var(--accent-orange);font-size:0.75rem"'
        : 'style="font-size:0.75rem;color:var(--text-muted)"';
      
      const orTestHtml = r.or_test_name ? `<br><span style="font-size:0.65rem;opacity:0.7">${r.or_test_name}</span>` : "";

      return `
        <tr>
          <td class="col-var">
            ${r.label || r.name}
            <div style="font-size:0.7rem;color:var(--text-muted);font-weight:400">${r.var_type.replaceAll('_', ' ')}</div>
          </td>
          <td>${totalStr}</td>
          <td>${missStr}</td>
          <td>${g0Str}</td>
          <td>${g1Str}</td>
          <td ${pClass}>${pValFmt}</td>
          <td ${testStyle}>${r.test_name || "—"}${orTestHtml}</td>
          <td style="font-size:0.8rem;color:var(--text-secondary)">${effectHtml}</td>
        </tr>
      `;
    }).join("");
  }

  function renderFindings() {
    const correction = filterCorrection ? filterCorrection.value : "none";
    const sigVars = tableData.filter(r => {
      let pVal = r.p_value;
      if (correction === "bonferroni") pVal = r.p_value_bonferroni;
      else if (correction === "fdr_bh") pVal = r.p_value_bh;
      return pVal !== null && pVal < 0.05;
    });
    
    if (sigVars.length === 0) {
      findingsGrid.innerHTML = `<div style="grid-column:1/-1;color:var(--text-muted)">No statistically significant findings (p < 0.05) found in this dataset.</div>`;
      return;
    }

    findingsGrid.innerHTML = sigVars.map(r => {
      let effectHtml = "";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null && Object.keys(r.extra_stats.or).length > 0) effectHtml = `OR: ${r.extra_stats.or.or.toFixed(2)}`;
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

      let pValFmt = r.p_value_fmt;
      if (correction === "bonferroni") pValFmt = r.p_value_bonferroni_fmt;
      else if (correction === "fdr_bh") pValFmt = r.p_value_bh_fmt;

      return `
        <div class="finding-card reveal">
          <div class="finding-header">
            <span class="finding-title">${r.label || r.name}</span>
            <span class="finding-pval">p = ${pValFmt}</span>
          </div>
          <div class="finding-body">
            <div><strong>${g0Name}:</strong> ${g0Str}</div>
            <div><strong>${g1Name}:</strong> ${g1Str}</div>
            ${effectHtml ? `<div style="margin-top:0.5rem;font-size:0.85rem;color:var(--text-muted)">${effectHtml}</div>` : ''}
          </div>
        </div>
      `;
    }).join("");
    observeReveal(findingsGrid);
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
    document.getElementById("multi-epv").textContent = data.epv;
    document.getElementById("multi-n-features").textContent = `${data.lasso?.n_features_selected || data.n_features_selected || 0}/${data.n_features_total}`;
    document.getElementById("multi-firth-sig").textContent = data.firth.variables.filter(v => v.significant).length;
    document.getElementById("multi-std-sig").textContent = data.standard.variables.filter(v => v.significant && v.name !== "Intercept").length;

    // LASSO stats and plot
    if (data.lasso) {
      document.getElementById("lasso-auc").textContent = data.lasso.auc_cv || "—";
      document.getElementById("lasso-brier").textContent = data.lasso.brier_score_cv || "—";
      document.getElementById("lasso-c").textContent = data.lasso.best_C || "—";
      
      if (data.lasso.calibration) {
        const traceTrue = {
          x: data.lasso.calibration.prob_pred,
          y: data.lasso.calibration.prob_true,
          mode: 'markers+lines',
          name: 'Calibration curve',
          marker: { color: '#63b3ed', size: 8 }
        };
        const tracePerfect = {
          x: [0, 1],
          y: [0, 1],
          mode: 'lines',
          name: 'Perfectly calibrated',
          line: { color: 'gray', dash: 'dash' }
        };
        const layout = {
          title: "LASSO 10-fold CV Calibration Curve",
          xaxis: { title: "Mean Predicted Probability" },
          yaxis: { title: "Fraction of Positives" },
          margin: { l: 50, r: 20, t: 40, b: 50 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: '#8b97b0' },
          showlegend: true,
          legend: { x: 0.05, y: 0.95 }
        };
        Plotly.newPlot("calibration-plot", [tracePerfect, traceTrue], layout, { responsive: true });
      }
      renderMultiTable("lasso", data.lasso.variables, false);
    }

    // Firth meta
    document.getElementById("multi-firth-meta").textContent = `Method: ${data.firth.method}. ${data.firth.n_iterations} iterations.`;

    // Standard meta
    let stdMeta = `Method: ${data.standard.method}. Pseudo R² = ${data.standard.pseudo_r2}. Log-likelihood = ${data.standard.log_likelihood}.`;
    if (data.standard.nagelkerke_r2) stdMeta += ` Nagelkerke R² = ${data.standard.nagelkerke_r2}.`;
    if (data.standard.auc) stdMeta += ` AUC = ${data.standard.auc}.`;
    if (data.standard.hl_p_value !== null) {
      stdMeta += ` HL test p = ${data.standard.hl_p_value}.`;
    } else {
      stdMeta += ` HL test skipped: insufficient prediction bins (n≤2).`;
    }
    document.getElementById("multi-std-meta").textContent = stdMeta;

    // Render both tables
    renderMultiTable("firth", data.firth.variables, false);
    renderMultiTable("std", data.standard.variables, true);

    // Interpretation cards
    renderMultiInterpretation(data);
  }

  function renderMultiTable(idPrefix, variables, showCrude = false) {
    const thead = document.getElementById(`thead-${idPrefix}`);
    const tbody = document.getElementById(`tbody-${idPrefix}`);
    if (!thead || !tbody) return;

    let headHtml = `<tr>
      <th>Predictor</th>
      <th>Coef (β)</th>
      <th>SE</th>`;
    
    if (showCrude) {
      headHtml += `<th>Crude OR (95% CI)</th>`;
    }
    
    headHtml += `<th>Adj OR</th>
      <th>95% CI</th>
      <th>p-value</th>
    </tr>`;
    thead.innerHTML = headHtml;

    tbody.innerHTML = variables.map(v => {
      const pClass = v.significant ? 'style="color:var(--accent-green);font-weight:600"' : '';
      const ciStr = (v.ci_lo !== undefined && v.ci_hi !== undefined) ? `[${v.ci_lo}–${v.ci_hi}]` : '—';
      const orDisplay = (v.or !== undefined) ? (v.or > 1 ? `<span style="color:var(--accent-red)">${v.or}</span>` : v.or < 1 ? `<span style="color:var(--accent-green)">${v.or}</span>` : v.or) : '—';
      const seDisplay = v.se !== undefined ? v.se : '—';
      const pValDisplay = v.p_value !== undefined ? v.p_value : '—';
      
      let crudeHtml = "";
      if (showCrude) {
        if (v.crude_or !== undefined) {
          crudeHtml = `<td style="font-family:var(--font-mono);font-size:0.82rem">${v.crude_or} [${v.crude_ci_lo}–${v.crude_ci_hi}]</td>`;
        } else {
          crudeHtml = `<td style="font-family:var(--font-mono);font-size:0.82rem;color:var(--text-muted)">—</td>`;
        }
      }

      return `<tr>
        <td class="col-var">${v.name}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${v.coef}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${seDisplay}</td>
        ${crudeHtml}
        <td style="font-family:var(--font-mono);font-weight:600">${orDisplay}</td>
        <td style="font-family:var(--font-mono);font-size:0.82rem">${ciStr}</td>
        <td ${pClass} style="font-family:var(--font-mono)">${pValDisplay}</td>
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

    // 0. EPV and Model Choice
    const hasSeparation = data.standard && data.standard.error && data.standard.error.toLowerCase().includes("separation");
    let expChoice = "";
    let expReason = "";

    if (hasSeparation) {
        expChoice = "FIRTH 🔴";
        expReason = "(separation detected)";
    } else if (data.epv < 5) {
        expChoice = "FIRTH 🔴";
        expReason = "(EPV critical)";
    } else if (data.epv < 10) {
        expChoice = "FIRTH 🟡";
        expReason = "(EPV borderline, Firth safer)";
    } else if (data.epv < 15) {
        expChoice = "STANDARD MLE 🟡";
        expReason = "(warn: borderline EPV)";
    } else {
        expChoice = "STANDARD MLE 🟢";
        expReason = "";
    }

    bullets.push(`<strong>📊 Model Recommendation (Events Per Variable = ${data.epv})</strong><br>
      <div style="background:var(--bg-main); padding:1rem; border-radius:6px; margin-top:0.75rem; font-family:var(--font-mono); font-size:0.85rem; border:1px solid var(--border-color); line-height:1.5;">
        <div style="margin-bottom:0.25rem"><strong>IF objective == PREDICTIVE:</strong></div>
        <div style="padding-left:1.5rem; color:var(--text-muted)">→ LASSO + 10-fold CV</div>
        <div style="padding-left:1.5rem; color:var(--text-muted); margin-bottom:0.75rem">→ report: AUC, Brier score, calibration plot</div>
        <div style="margin-bottom:0.25rem"><strong>IF objective == EXPLANATORY:</strong></div>
        <div style="padding-left:1.5rem; margin-bottom:0.25rem">→ ${expChoice} <span style="color:var(--text-muted)">${expReason}</span></div>
        <div style="padding-left:1.5rem; color:var(--text-muted)">→ report: OR, 95% CI, p, H-L test, Nagelkerke R²</div>
      </div>
    `);

    // 1. LASSO
    bullets.push(`<strong>🎯 LASSO Feature Selection (Prediction)</strong> — For building a sparse prediction model (e.g., clinical scoring tool), LASSO (C=${data.lasso.best_C}) shrunk the ${data.n_features_total} candidates down to <strong>${data.lasso.n_features_selected}</strong> independent predictors. LASSO ORs are deliberately shrunk (biased towards 1) to prevent overfitting, so they are not used for causal interpretation.`);

    // 2. Agreement
    bullets.push(`<strong>🤝 Firth vs Standard Agreement</strong> — Both methods agree on <strong>${agree.length} significant predictor${agree.length !== 1 ? 's' : ''}</strong>: ${agree.join(", ") || "none"}. Firth provides more conservative profile-likelihood CIs and handles small samples or rare events better. Standard MLE provides goodness-of-fit metrics (Nagelkerke R² = ${data.standard.nagelkerke_r2 || '-'}) and discrimination power (AUC = ${data.standard.auc || '-'}) required by medical journals.`);

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
      bullets.push(`<strong>📏 Baseline (Intercept)</strong> — OR = <strong>${intercept.or}</strong> [${intercept.ci_lo}–${intercept.ci_hi}], p = ${intercept.p_value}. Baseline SIP odds when all predictors are at reference level.`);
    }

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
  [filterType, filterSig, filterCorrection].forEach(el => {
    if (el) el.addEventListener("change", () => {
      renderTable();
      renderFindings();
    });
  });
  searchVar.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      renderTable();
      renderFindings();
    }, 200);
  });

  btnExport.addEventListener("click", () => {
    if (!tableData.length) return;
    const groupKeys = Object.keys(metaData.group_counts || {});
    const g0Name = groupKeys.length > 0 ? groupKeys[0] : "Group 0";
    const g1Name = groupKeys.length > 1 ? groupKeys[1] : "Group 1";

    function csvEscape(str) {
      if (str === null || str === undefined) return "";
      const s = String(str);
      if (s.includes('"') || s.includes(',') || s.includes('\n')) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    }

    const csvRows = [];
    csvRows.push(["Variable", "Type", "Total", g0Name, g1Name, "p-value", "Effect_Type", "Effect_Size", "Effect_CI_Low", "Effect_CI_High"].map(csvEscape).join(","));
    
    tableData.forEach(r => {
      let ciLo = "", ciHi = "", effectType = "", effectSize = "";
      if (r.extra_stats) {
        if (r.extra_stats.or !== undefined && r.extra_stats.or !== null && Object.keys(r.extra_stats.or).length > 0) {
          effectType = "OR";
          effectSize = r.extra_stats.or.or ?? "";
          ciLo = r.extra_stats.or.ci_lo ?? "";
          ciHi = r.extra_stats.or.ci_hi ?? "";
          // Add p-value and method to csv if we decide to add those columns later. Currently they aren't in the header.
        } else if (r.extra_stats.smd !== undefined && r.extra_stats.smd !== null) {
          effectType = "SMD";
          effectSize = r.extra_stats.smd ?? "";
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
        csvEscape(r.name),
        csvEscape(r.var_type),
        csvEscape(totalStr),
        csvEscape(g0Str || ''),
        csvEscape(g1Str || ''),
        csvEscape(r.p_value),
        csvEscape(effectType),
        csvEscape(effectSize),
        csvEscape(ciLo),
        csvEscape(ciHi)
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

  if (btnExportLatex) {
    btnExportLatex.addEventListener("click", async () => {
      const res = await fetch("data/tableone.tex");
      if (!res.ok) return alert("LaTeX file not yet generated. Run the analysis pipeline first.");
      const text = await res.text();
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sip_tableone_${new Date().toISOString().slice(0,10)}.tex`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }


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

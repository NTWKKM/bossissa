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
  const pageTableOne = document.getElementById("page-tableone");
  const pageCharts = document.getElementById("page-charts");
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

  // 1. Fetch Data
  try {
    const [metaRes, tableRes, chartsRes] = await Promise.all([
      fetch("data/metadata.json"),
      fetch("data/tableone.json"),
      fetch("data/charts.json").catch(() => ({ ok: false })) // Charts might fail if not generated yet
    ]);

    if (!metaRes.ok || !tableRes.ok) throw new Error("Data files not found");

    metaData = await metaRes.json();
    tableData = await tableRes.json();
    
    if (chartsRes && chartsRes.ok) {
      chartsData = await chartsRes.json();
    }

    populateHero();
    renderTable();
    renderFindings();
    
    // Hide loading, show table
    loadingState.style.display = "none";
    table.hidden = false;
    
    // Render charts if active or preload
    if (chartsData.length > 0) {
      chartsLoading.style.display = "none";
      renderCharts();
    } else {
      chartsLoading.innerHTML = "<p>No chart data available yet.</p>";
    }

  } catch (err) {
    console.error(err);
    loadingState.innerHTML = `<p style="color:var(--accent-red)">Error loading analysis data. Ensure the GitHub Action has run.</p>`;
    chartsLoading.innerHTML = `<p style="color:var(--accent-red)">Error loading chart data.</p>`;
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

    const g0Name = metaData.group_labels["0"] || "0";
    const g1Name = metaData.group_labels["1"] || "1";
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
            <div style="font-size:0.7rem;color:var(--text-muted);font-weight:400">${r.var_type.replace('_', ' ')}</div>
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
      const g0Name = metaData.group_labels["0"] || "0";
      const g1Name = metaData.group_labels["1"] || "1";

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

  // 3. Tab Navigation
  function switchTab(tabId) {
    if (tabId === "tableone") {
      tabTableOne.classList.add("active");
      tabTableOne.setAttribute("aria-selected", "true");
      tabCharts.classList.remove("active");
      tabCharts.setAttribute("aria-selected", "false");
      
      pageTableOne.hidden = false;
      pageCharts.hidden = true;
    } else {
      tabCharts.classList.add("active");
      tabCharts.setAttribute("aria-selected", "true");
      tabTableOne.classList.remove("active");
      tabTableOne.setAttribute("aria-selected", "false");
      
      pageCharts.hidden = false;
      pageTableOne.hidden = true;
      
      // Re-trigger layout for Plotly to ensure it sizes correctly if it was hidden
      // Use setTimeout to allow the browser to paint the display:block first
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  }

  tabTableOne.addEventListener("click", () => switchTab("tableone"));
  tabCharts.addEventListener("click", () => switchTab("charts"));

  // 4. Plotly Charts Rendering
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

      // We clone the layout to ensure Plotly doesn't mutate our source object in weird ways
      const layout = Object.assign({}, spec.layout);
      const config = { responsive: true, displayModeBar: false };

      Plotly.newPlot(containerId, spec.data, layout, config);
    });
  }

  // 5. Interactivity
  [filterType, filterSig, searchVar].forEach(el => {
    el.addEventListener("input", renderTable);
    el.addEventListener("change", renderTable);
  });

  btnExport.addEventListener("click", () => {
    if (!tableData.length) return;
    const g0Name = metaData.group_labels["0"] || "0";
    const g1Name = metaData.group_labels["1"] || "1";

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

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
});

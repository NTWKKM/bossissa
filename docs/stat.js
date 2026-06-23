// stat.js - Bossissa SIP Frequency Stats Frontend
document.addEventListener("DOMContentLoaded", async () => {
  const loadingState = document.getElementById("loading-state");
  const contentArea = document.getElementById("content-area");
  const footerTs = document.getElementById("footer-ts");

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

  let statData = null;

  try {
    const res = await fetch("data/stat_freq.json");
    if (!res.ok) throw new Error("Stat data not found");
    statData = await res.json();

    document.getElementById("meta-line").innerHTML = `
      Data updated: <span class="ts">${new Date(statData.generated_at).toLocaleString()}</span> | Total Patients: ${statData.total_n}
    `;
    footerTs.textContent = `Last run: ${new Date(statData.generated_at).toLocaleString()}`;

    // Render tables
    renderTable("inclusion", statData.inclusion, statData.total_n);
    renderTable("hx", statData.hx_psych, statData.total_n);
    renderTable("sip", statData.sip_all, statData.total_n);

    loadingState.style.display = "none";
    contentArea.hidden = false;

  } catch (err) {
    console.error(err);
    loadingState.innerHTML = `<p style="color:var(--accent-red)">Error loading stat data. Ensure the GitHub Action has run the new stat_generator.py.</p>`;
  }

  function renderTable(idPrefix, groupData, totalN) {
    const thead = document.getElementById(`thead-${idPrefix}`);
    const tbody = document.getElementById(`tbody-${idPrefix}`);
    
    if (!groupData || !groupData.results) return;

    // Build headers based on group_labels
    // group_labels might be {"0": "Not Met", "1": "Met"}
    // Sort keys or just use them as they appear in group_counts? Let's use group_labels
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

    // Build body
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
            <div style="font-size:0.7rem;color:var(--text-muted);font-weight:400">${r.var_type.replace('_', ' ')}</div>
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

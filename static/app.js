function fmtMoney(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const n = Number(v);
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtNum(v, digits=8) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const n = Number(v);
  return n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

function showAlert(type, msg) {
  const el = document.getElementById("alert");
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  el.classList.remove("d-none");
}

function hideAlert() {
  const el = document.getElementById("alert");
  el.classList.add("d-none");
}

document.getElementById("frm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  hideAlert();

  const status = document.getElementById("status");
  status.textContent = "Processando...";

  const file = document.getElementById("file").files[0];
  if (!file) {
    showAlert("warning", "Selecione o arquivo .xlsx.");
    status.textContent = "";
    return;
  }

  const form = new FormData();
  form.append("file", file);
  form.append("pair", document.getElementById("pair").value || "");
  form.append("current_price", document.getElementById("current_price").value || "");

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();

    if (!data.ok) {
      showAlert("danger", data.error || "Erro.");
      status.textContent = "";
      return;
    }

    const r = data.result;
    document.getElementById("results").classList.remove("d-none");

    document.getElementById("selectedPair").textContent = data.selected_pair;
    
    const realizedEl = document.getElementById("realized");
    realizedEl.textContent = `${fmtMoney(r.realized_pl)} ${r.quote}`;
    realizedEl.classList.remove("positive", "negative");
    realizedEl.classList.add(r.realized_pl >= 0 ? "positive" : "negative");
    
    document.getElementById("baseAsset").textContent = r.base;
    document.getElementById("quoteAsset").textContent = r.quote;
    document.getElementById("quoteAsset2").textContent = r.quote;

    document.getElementById("posQty").textContent = fmtNum(r.position_qty, 8);
    document.getElementById("posCost").textContent = fmtMoney(r.position_cost);
    document.getElementById("avgCost").textContent = fmtMoney(r.avg_cost);

    const unrealizedEl = document.getElementById("unrealized");
    if (r.unrealized_pl !== null) {
      unrealizedEl.textContent = `${fmtMoney(r.unrealized_pl)} ${r.quote}`;
      unrealizedEl.classList.remove("positive", "negative");
      unrealizedEl.classList.add(r.unrealized_pl >= 0 ? "positive" : "negative");
    }

    document.getElementById("currentPrice").textContent = r.current_price ? `${fmtMoney(r.current_price)} ${r.quote}/${r.base}` : "—";
    document.getElementById("priceSource").textContent = data.price_source;

    const tbody = document.getElementById("tbody");
    tbody.innerHTML = "";
    for (const row of data.rows) {
      const tr = document.createElement("tr");
      const fee = row.fee_asset ? `${fmtNum(row.fee_qty, 8)} ${row.fee_asset}` : "—";
      tr.innerHTML = `
        <td class="text-nowrap">${row.date}</td>
        <td><span class="badge ${row.type === "BUY" ? "text-bg-success" : "text-bg-danger"}">${row.type}</span></td>
        <td>${fmtNum(row.filled, 8)} ${row.base}</td>
        <td>${fmtMoney(row.total)} ${row.quote}</td>
        <td>${fmtMoney(row.avg_price)} ${row.quote}/${row.base}</td>
        <td>${fee}</td>
      `;
      tbody.appendChild(tr);
    }

    document.getElementById("notes").innerHTML = (data.notes || []).map(n => `• ${n}`).join("<br/>");
    status.textContent = "Pronto.";

    if (data.pl_series) {
      renderChart(data.pl_series);
    }

  } catch (e) {
    showAlert("danger", `Falha: ${e}`);
    status.textContent = "";
  }
});


let chart;

function renderChart(series) {
  const ctx = document.getElementById("plChart").getContext("2d");

  const labels = series.map(x => x.date);
  const data = series.map(x => x.pl);

  if (chart) chart.destroy();

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "P/L acumulado",
        data,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: true }
      }
    }
  });
}

// Dark theme toggle
// document.addEventListener("DOMContentLoaded", function() {
//   const themeToggle = document.getElementById("themeToggle");
//   const html = document.documentElement;
  
//   // Carregar tema do localStorage
//   const savedTheme = localStorage.getItem("theme") || "light";
//   html.setAttribute("data-bs-theme", savedTheme);
//   updateThemeButton(savedTheme);
  
//   // Alternar tema
//   themeToggle.addEventListener("click", function() {
//     const currentTheme = html.getAttribute("data-bs-theme");
//     const newTheme = currentTheme === "light" ? "dark" : "light";
//     html.setAttribute("data-bs-theme", newTheme);
//     localStorage.setItem("theme", newTheme);
//     updateThemeButton(newTheme);
//   });
  
//   function updateThemeButton(theme) {
//     themeToggle.textContent = theme === "light" ? "🌙" : "☀️";
//   }
// });

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);

  const btn = document.getElementById("themeToggle");
  btn.textContent = theme === "dark" ? "☀️ Light" : "🌙 Dark";
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
}

document.getElementById("themeToggle").addEventListener("click", toggleTheme);

// carregar preferência salva
const savedTheme = localStorage.getItem("theme") || "dark";
applyTheme(savedTheme);

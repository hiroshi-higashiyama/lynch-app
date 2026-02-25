document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("calc-form");
  const input = document.getElementById("stock-code");
  const btn = document.getElementById("calc-btn");
  const loading = document.getElementById("loading");
  const errorMsg = document.getElementById("error-msg");
  const results = document.getElementById("results");

  form.addEventListener("submit", async () => {
    const code = input.value.trim();
    if (!/^\d{4}$/.test(code)) {
      showError("有効な4桁の証券コードを入力してください。");
      return;
    }

    hideError();
    hideResults();
    showLoading();
    btn.disabled = true;

    try {
      const resp = await fetch("/api/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stock_code: code }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        showError(data.error || "エラーが発生しました。");
        return;
      }

      renderResults(data);
    } catch {
      showError("通信エラーが発生しました。ネットワーク接続を確認してください。");
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });

  // Allow Enter key
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Only allow digits
  input.addEventListener("input", () => {
    input.value = input.value.replace(/\D/g, "");
  });

  function showLoading() {
    loading.classList.remove("hidden");
  }
  function hideLoading() {
    loading.classList.add("hidden");
  }
  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove("hidden");
  }
  function hideError() {
    errorMsg.classList.add("hidden");
  }
  function hideResults() {
    results.classList.add("hidden");
  }

  function renderResults(data) {
    // Company header
    document.getElementById("company-name").textContent =
      data.company_name || "不明";
    document.getElementById("result-code").textContent = data.stock_code;
    document.getElementById("result-price").textContent =
      data.stock_price_fmt || "N/A";

    // Index cards
    const cardsContainer = document.getElementById("index-cards");
    cardsContainer.innerHTML = "";

    for (const idx of data.indices) {
      const card = document.createElement("div");
      card.className = `index-card ${idx.evaluation_class}`;
      card.innerHTML = `
        <div class="card-title">${escapeHtml(idx.name)}</div>
        <div class="card-value">${escapeHtml(idx.index_value_fmt)}</div>
        <span class="eval-label ${idx.evaluation_class}">${escapeHtml(idx.evaluation)}</span>
        <div class="card-growth">成長率: ${escapeHtml(idx.growth_rate_fmt)}%</div>
      `;
      cardsContainer.appendChild(card);
    }

    // Input data table
    const tbody = document.querySelector("#input-data-table tbody");
    tbody.innerHTML = "";

    const inputRows = [
      ["PER", data.input_data.per, data.data_source_yahoo],
      ["配当利回り (%)", data.input_data.dividend_yield, data.data_source_yahoo],
      ["EPS（当期実績）", data.input_data.eps_current, data.data_source_edinet],
      ["EPS（前期）", data.input_data.eps_previous, data.data_source_edinet],
      ["EPS（来期予想）", data.input_data.eps_forecast, data.data_source_edinet],
      [
        "経常利益（当期）",
        data.input_data.ordinary_income_current,
        data.data_source_edinet,
      ],
      [
        "経常利益（前期）",
        data.input_data.ordinary_income_previous,
        data.data_source_edinet,
      ],
      [
        "経常利益（前々期）",
        data.input_data.ordinary_income_two_years_ago,
        data.data_source_edinet,
      ],
      [
        "経常利益（来期予想）",
        data.input_data.ordinary_income_forecast,
        data.data_source_edinet,
      ],
    ];

    for (const [label, value, source] of inputRows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(label)}</td>
        <td>${escapeHtml(value)}</td>
        <td>${escapeHtml(source)}</td>
      `;
      tbody.appendChild(tr);
    }

    // Calculation process
    const processContainer = document.getElementById("calc-process");
    processContainer.innerHTML = "";

    for (const idx of data.indices) {
      const step = document.createElement("div");
      step.className = "calc-step";
      step.innerHTML = `
        <div class="step-title">${escapeHtml(idx.name)}</div>
        <div class="step-growth">成長率: ${escapeHtml(idx.growth_formula)}</div>
        <div class="step-formula">リンチ指数: ${escapeHtml(idx.formula)}</div>
      `;
      processContainer.appendChild(step);
    }

    results.classList.remove("hidden");
  }

  function escapeHtml(str) {
    if (str == null) return "";
    const text = String(str);
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }
});

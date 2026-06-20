const formatter = new Intl.NumberFormat("en-US");
const currency = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

const peakHours = new Set(["12:00", "13:00", "18:00", "19:00"]);
let currentView = "pm";
let latestData = null;

const roleViews = {
  pm: {
    eyebrow: "Product Management",
    title: "Peak demand and customer impact",
    summary: "Track whether lunch and dinner demand spikes create product, store, or customer-experience risk.",
    question: "Which peak windows need product or staffing decisions?",
    signal: "Peak-window orders vs. baseline, top sellers, store load.",
    path: "S3 raw events -> Paimon latest state -> dashboard exports",
    hourlyCopy: "PM view highlights where demand spikes should change menu, inventory, or staffing plans.",
    leftTitle: "Demand pressure by store",
    leftCopy: "Stores ranked by order-pressure ratio during peak hours.",
    rightTitle: "Customer-impact alerts",
    rightCopy: "Peak windows that likely need product or operational intervention.",
    bottomLeftTitle: "Product demand",
    bottomLeftCopy: "Top products to watch for stockout or promotion opportunities.",
    bottomRightTitle: "PM action queue",
    bottomRightCopy: "Decisions a PM would take from the current signal.",
    actions: [
      ["Protect hero SKUs", "Increase safety stock for top peak products.", "High"],
      ["Tune lunch promise", "Adjust ETA copy for stores above 4x pressure.", "Today"],
      ["Review peak bundles", "Bundle top drinks and food items for 12:00 and 18:00.", "Next test"],
    ],
  },
  "data-engineer": {
    eyebrow: "Data Engineering",
    title: "Pipeline freshness and lakehouse state",
    summary: "Observe raw ingestion, quality gates, Paimon merge outputs, and serving export readiness.",
    question: "Is the peak signal trustworthy and ready for downstream consumers?",
    signal: "Quality gate passed, Paimon pressure tables populated, exports refreshed.",
    path: "Airflow -> EMR Serverless Spark -> Apache Paimon -> S3 serving JSON",
    hourlyCopy: "Data engineering view checks whether event volume and pressure tables match the generated traffic shape.",
    leftTitle: "Paimon pressure rows",
    leftCopy: "Hourly store pressure from the mutable lakehouse state.",
    rightTitle: "Pipeline-derived alerts",
    rightCopy: "Rows emitted by the peak detection job after Paimon merge.",
    bottomLeftTitle: "Serving exports",
    bottomLeftCopy: "Views expected by dashboards and downstream consumers.",
    bottomRightTitle: "DE action queue",
    bottomRightCopy: "Operational checks for data reliability.",
    actions: [
      ["Validate S3 partition", "Confirm raw orders uploaded under orders/ for replay.", "Ready"],
      ["Check Paimon merge", "Latest tables should collapse duplicate order state.", "Ready"],
      ["Refresh export contract", "dashboard.json mirrors S3 serving export shape.", "Ready"],
    ],
  },
  "ml-engineer": {
    eyebrow: "ML Engineering",
    title: "Peak features and alert candidates",
    summary: "Inspect pressure ratios, product movement, and store-hour spikes that can become model features.",
    question: "Which store-hour features explain peak demand and should feed forecasting?",
    signal: "Pressure ratio, product mix, store load, and alert severity.",
    path: "Paimon features -> pressure aggregates -> model candidates",
    hourlyCopy: "ML view treats each store-hour as a feature row for forecasting, anomaly detection, or staffing prediction.",
    leftTitle: "Feature candidates",
    leftCopy: "Store-hour rows with strong signal for model training.",
    rightTitle: "Label candidates",
    rightCopy: "Peak alerts that can be reviewed as anomaly labels.",
    bottomLeftTitle: "Product features",
    bottomLeftCopy: "High-volume products that influence demand forecasts.",
    bottomRightTitle: "ML action queue",
    bottomRightCopy: "Feature engineering and model-readiness tasks.",
    actions: [
      ["Add lag features", "Compare current hour to prior same-day and prior-week baselines.", "Feature"],
      ["Create alert labels", "Use pressure threshold crossings as weak anomaly labels.", "Label"],
      ["Monitor drift", "Watch product mix changes between lunch and dinner peaks.", "Drift"],
    ],
  },
  sre: {
    eyebrow: "SRE / Operations",
    title: "Operational pressure and incident risk",
    summary: "Watch the stores and hours most likely to overload fulfillment, APIs, or downstream jobs.",
    question: "Where would an incident happen first during a demand surge?",
    signal: "Critical pressure alerts, peak order concentration, export freshness.",
    path: "CloudWatch logs + EMR Serverless state + S3 exports",
    hourlyCopy: "SRE view emphasizes peak windows that may stress compute, store operations, and alerting pipelines.",
    leftTitle: "Incident hotspots",
    leftCopy: "Stores with the highest pressure ratios.",
    rightTitle: "Critical alerts",
    rightCopy: "Prioritized alert stream for operational triage.",
    bottomLeftTitle: "Capacity drivers",
    bottomLeftCopy: "Products and stores that amplify peak load.",
    bottomRightTitle: "SRE action queue",
    bottomRightCopy: "Runbook-style response steps.",
    actions: [
      ["Scale workers", "Increase EMR Serverless max capacity before known peak windows.", "Before peak"],
      ["Watch retries", "Investigate failed EMR job runs or S3 throttling.", "Live"],
      ["Escalate stores", "Notify store owners when pressure ratio exceeds 4x.", "Critical"],
    ],
  },
  leadership: {
    eyebrow: "Leadership",
    title: "Business impact summary",
    summary: "A compressed view of peak demand, revenue concentration, and operational risk.",
    question: "Is peak demand creating upside, risk, or both?",
    signal: "Revenue, alert count, peak concentration, and store distribution.",
    path: "AWS lakehouse metrics -> executive operating view",
    hourlyCopy: "Leadership view shows how much of the day is dominated by lunch and dinner demand.",
    leftTitle: "Peak concentration",
    leftCopy: "Where the business is most exposed during high-demand windows.",
    rightTitle: "Risk register",
    rightCopy: "Critical pressure alerts summarized for leadership review.",
    bottomLeftTitle: "Revenue drivers",
    bottomLeftCopy: "Products responsible for the largest sales contribution.",
    bottomRightTitle: "Leadership action queue",
    bottomRightCopy: "Strategic follow-up from the current operating signal.",
    actions: [
      ["Approve capacity plan", "Treat lunch/dinner as planned surge windows.", "Decision"],
      ["Fund forecasting", "Move pressure rows into ML demand prediction.", "Investment"],
      ["Track reliability", "Add SLA reporting around peak export freshness.", "KPI"],
    ],
  },
};

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function metricCard(label, value) {
  const article = document.createElement("article");
  article.className = "metric";
  article.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
  return article;
}

function renderMetrics(summary, viewKey) {
  const metrics = {
    pm: [
      ["Total orders", formatter.format(summary.total_orders)],
      ["Peak-window orders", formatter.format(summary.peak_orders)],
      ["Gross sales", currency.format(summary.total_sales)],
      ["Peak alerts", formatter.format(summary.alert_count)],
    ],
    "data-engineer": [
      ["Raw events", formatter.format(summary.total_orders)],
      ["Paimon pressure rows", "96"],
      ["Serving views", "5"],
      ["Stream mode", latestData?.live ? "Live replay" : "Static export"],
    ],
    "ml-engineer": [
      ["Feature rows", "96 store-hours"],
      ["Weak labels", formatter.format(summary.alert_count)],
      ["Peak examples", formatter.format(summary.peak_orders)],
      ["Product signals", "6 SKUs"],
    ],
    sre: [
      ["Critical windows", formatter.format(summary.alert_count)],
      ["Peak orders", formatter.format(summary.peak_orders)],
      ["Stores monitored", formatter.format(summary.store_count)],
      ["Export status", "Healthy"],
    ],
    leadership: [
      ["Revenue", currency.format(summary.total_sales)],
      ["Orders", formatter.format(summary.total_orders)],
      ["Peak share", `${Math.round((summary.peak_orders / summary.total_orders) * 100)}%`],
      ["Active stores", formatter.format(summary.store_count)],
    ],
  };

  const target = document.getElementById("role-metrics");
  target.innerHTML = "";
  metrics[viewKey].forEach(([label, value]) => target.appendChild(metricCard(label, value)));
}

function renderHourlyChart(rows) {
  const maxOrders = Math.max(...rows.map((row) => row.orders));
  const chart = document.getElementById("hourly-chart");
  chart.innerHTML = "";

  rows.forEach((row) => {
    const bar = document.createElement("div");
    bar.className = `bar ${peakHours.has(row.hour) ? "peak" : ""}`;
    bar.title = `${row.hour}: ${formatter.format(row.orders)} orders`;

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.height = `${Math.max(3, (row.orders / maxOrders) * 100)}%`;

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = row.hour.slice(0, 2);

    bar.append(fill, label);
    chart.appendChild(bar);
  });
}

function rankRow(title, subtitle, value) {
  const row = document.createElement("div");
  row.className = "rank-row";
  row.innerHTML = `
    <div>
      <strong>${title}</strong>
      <span>${subtitle}</span>
    </div>
    <div class="rank-value">${value}</div>
  `;
  return row;
}

function renderRankList(id, rows) {
  const target = document.getElementById(id);
  target.innerHTML = "";
  rows.forEach((row) => target.appendChild(rankRow(row.title, row.subtitle, row.value)));
}

function pressureRows(data) {
  return data.store_pressure
    .slice()
    .sort((a, b) => b.pressure_ratio - a.pressure_ratio)
    .slice(0, 8)
    .map((row) => ({
      title: row.store_id,
      subtitle: `${row.hour} - ${formatter.format(row.orders)} orders`,
      value: `${row.pressure_ratio}x`,
    }));
}

function productRows(data) {
  return data.top_products.map((row) => ({
    title: row.product_id,
    subtitle: `${formatter.format(row.units_sold)} units`,
    value: currency.format(row.gross_sales),
  }));
}

function storeRows(data) {
  return data.store_totals.map((row) => ({
    title: row.store_id,
    subtitle: "Total orders",
    value: formatter.format(row.orders),
  }));
}

function servingRows() {
  return [
    { title: "product_leaderboard", subtitle: "S3 JSON + Parquet export", value: "Ready" },
    { title: "store_daily_summary", subtitle: "S3 JSON + Parquet export", value: "Ready" },
    { title: "peak_pressure", subtitle: "Store-hour pressure rows", value: "Ready" },
    { title: "peak_alerts", subtitle: "Threshold crossings", value: "Ready" },
  ];
}

function renderDetailTable(rows, viewKey) {
  const head = document.getElementById("detail-head");
  const body = document.getElementById("detail-table");
  head.innerHTML = "";
  body.innerHTML = "";

  const headers = viewKey === "data-engineer"
    ? ["Dataset", "Layer", "Freshness", "Status"]
    : ["Store", "Hour", "Orders", "Ratio", "Severity"];

  head.innerHTML = `<tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>`;

  if (viewKey === "data-engineer") {
    [
      ["orders_latest", "Paimon", "Latest state", "Ready"],
      ["order_items_latest", "Paimon", "Latest state", "Ready"],
      ["store_order_pressure_hourly", "Paimon", "Hourly", "Ready"],
      ["dashboard.json", "S3 export", "Near-real-time", "Ready"],
    ].forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = row.map((cell) => `<td>${cell}</td>`).join("");
      body.appendChild(tr);
    });
    return;
  }

  rows.slice(0, 8).forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.store_id}</td>
      <td>${row.hour}</td>
      <td>${formatter.format(row.orders)}</td>
      <td>${row.pressure_ratio}x</td>
      <td><span class="severity ${row.severity}">${row.severity}</span></td>
    `;
    body.appendChild(tr);
  });
}

function renderActions(view) {
  renderRankList("action-list", view.actions.map(([title, subtitle, value]) => ({ title, subtitle, value })));
}

function renderView(data, viewKey) {
  latestData = data;
  currentView = viewKey;
  const view = roleViews[viewKey];

  setText("role-eyebrow", view.eyebrow);
  setText("role-title", view.title);
  setText("role-summary", view.summary);
  setText("primary-question", view.question);
  setText("decision-signal", view.signal);
  setText("aws-path", view.path);
  setText("hourly-copy", view.hourlyCopy);
  setText("left-panel-title", view.leftTitle);
  setText("left-panel-copy", view.leftCopy);
  setText("right-panel-title", view.rightTitle);
  setText("right-panel-copy", view.rightCopy);
  setText("bottom-left-title", view.bottomLeftTitle);
  setText("bottom-left-copy", view.bottomLeftCopy);
  setText("bottom-right-title", view.bottomRightTitle);
  setText("bottom-right-copy", view.bottomRightCopy);

  renderMetrics(data.summary, viewKey);
  renderHourlyChart(data.hourly_orders);
  renderRankList("left-panel-list", viewKey === "data-engineer" ? servingRows() : pressureRows(data));
  renderDetailTable(data.alerts, viewKey);
  renderRankList("bottom-left-list", viewKey === "data-engineer" ? storeRows(data) : productRows(data));
  renderActions(view);
  renderLiveStatus(data);
}

function bindNavigation(data) {
  document.querySelectorAll("#role-nav button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("#role-nav button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderView(latestData || data, button.dataset.view);
    });
  });
}

function renderLiveStatus(data) {
  const pill = document.querySelector(".status-pill");
  if (!pill) return;

  if (!data.live) {
    pill.innerHTML = "<span></span> Static export loaded";
    return;
  }

  const percent = Math.round(data.live.progress * 100);
  pill.innerHTML = `<span></span> Live replay ${percent}% - ${formatter.format(data.live.processed_events)} events`;
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function shouldUseLiveApi() {
  return window.location.port === "8010" || window.location.search.includes("live=1");
}

async function loadInitialData() {
  if (!shouldUseLiveApi()) {
    return {
      data: await fetchJson("./data/dashboard.json"),
      liveApiAvailable: false,
    };
  }

  try {
    return {
      data: await fetchJson("/api/live-dashboard"),
      liveApiAvailable: true,
    };
  } catch {
    return {
      data: await fetchJson("./data/dashboard.json"),
      liveApiAvailable: false,
    };
  }
}

function startLivePolling() {
  window.setInterval(async () => {
    try {
      const data = await fetchJson("/api/live-dashboard");
      renderView(data, currentView);
    } catch {
      // Static hosting mode does not expose the live API.
    }
  }, 2000);
}

async function main() {
  const { data, liveApiAvailable } = await loadInitialData();

  bindNavigation(data);
  renderView(data, "pm");
  if (liveApiAvailable) {
    startLivePolling();
  }
}

main().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML("afterbegin", `<p class="load-error">${error.message}</p>`);
});

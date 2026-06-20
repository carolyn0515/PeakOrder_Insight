const formatter = new Intl.NumberFormat("en-US");
const currency = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

const peakHours = new Set(["12:00", "13:00", "18:00", "19:00"]);

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function renderMetrics(summary) {
  setText("total-orders", formatter.format(summary.total_orders));
  setText("peak-orders", formatter.format(summary.peak_orders));
  setText("gross-sales", currency.format(summary.total_sales));
  setText("alert-count", formatter.format(summary.alert_count));
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

function renderPressure(rows) {
  const target = document.getElementById("pressure-list");
  target.innerHTML = "";
  rows
    .slice()
    .sort((a, b) => b.pressure_ratio - a.pressure_ratio)
    .slice(0, 8)
    .forEach((row) => {
      target.appendChild(
        rankRow(row.store_id, `${row.hour} · ${formatter.format(row.orders)} orders`, `${row.pressure_ratio}x`),
      );
    });
}

function renderAlerts(rows) {
  const target = document.getElementById("alert-table");
  target.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.store_id}</td>
      <td>${row.hour}</td>
      <td>${formatter.format(row.orders)}</td>
      <td>${row.pressure_ratio}x</td>
      <td><span class="severity ${row.severity}">${row.severity}</span></td>
    `;
    target.appendChild(tr);
  });
}

function renderProducts(rows) {
  const target = document.getElementById("product-list");
  target.innerHTML = "";
  rows.forEach((row) => {
    target.appendChild(
      rankRow(row.product_id, `${formatter.format(row.units_sold)} units`, currency.format(row.gross_sales)),
    );
  });
}

function renderStores(rows) {
  const target = document.getElementById("store-list");
  target.innerHTML = "";
  rows.forEach((row) => {
    target.appendChild(rankRow(row.store_id, "Total orders", formatter.format(row.orders)));
  });
}

async function main() {
  const response = await fetch("./data/dashboard.json");
  const data = await response.json();

  renderMetrics(data.summary);
  renderHourlyChart(data.hourly_orders);
  renderPressure(data.store_pressure);
  renderAlerts(data.alerts);
  renderProducts(data.top_products);
  renderStores(data.store_totals);
}

main().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML("afterbegin", `<p class="load-error">${error.message}</p>`);
});

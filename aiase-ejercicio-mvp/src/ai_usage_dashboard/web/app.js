"use strict";

const fmtMoney = (n, ccy) =>
  n == null ? "—" : `${(ccy || "USD") === "USD" ? "$" : ""}${Number(n).toFixed(4)}`;
const fmtInt = (n) => (n == null ? "—" : Number(n).toLocaleString("es"));

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function renderKpis(r) {
  const root = document.getElementById("kpis");
  const cards = [
    [fmtMoney(r.total_calculated_cost, r.currency), "Total calculado"],
    [fmtInt(r.sessions_processed), "Sesiones procesadas"],
    [fmtInt(r.sessions_non_calculable), "No calculables"],
    [fmtInt(r.files_failed), "Archivos con error"],
  ];
  for (const [v, l] of cards) {
    const c = el("div", "card");
    c.appendChild(el("div", "value", v));
    c.appendChild(el("div", "label", l));
    root.appendChild(c);
  }
}

function renderIntegrity(r) {
  const root = document.getElementById("integrity");
  const ig = r.integrity || {};
  if (ig.unchanged) {
    root.innerHTML =
      `<span class="ok">✔ Fuentes sin cambios</span> — ${fmtInt(ig.files_checked)} archivos verificados (mtime/hash antes y después del scan).`;
  } else {
    root.innerHTML =
      `<span class="bad">✖ NO-GO técnico: las rutas fuente cambiaron</span> — ` +
      `modificados: ${(ig.modified || []).length}, añadidos: ${(ig.added || []).length}, eliminados: ${(ig.removed || []).length}.`;
  }
}

function renderBars(containerId, items, labelKey, valueKey, ccy) {
  const root = document.getElementById(containerId);
  root.innerHTML = "";
  const max = Math.max(0, ...items.map((i) => i[valueKey] || 0));
  if (!items.length) {
    root.appendChild(el("div", "label", "Sin datos calculables."));
    return;
  }
  for (const i of items) {
    const row = el("div", "bar-row");
    row.appendChild(el("div", null, i[labelKey] || "—"));
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = max > 0 ? `${((i[valueKey] || 0) / max) * 100}%` : "0%";
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el("div", "bar-val", fmtMoney(i[valueKey], ccy)));
    root.appendChild(row);
  }
}

function renderSessions(r) {
  const tbody = document.querySelector("#sessions tbody");
  tbody.innerHTML = "";
  for (const s of r.sessions) {
    const tr = document.createElement("tr");
    const calc = s.cost && s.cost.status === "calculado";
    const cells = [
      [s.day || s.started_at || "—", false],
      [s.model || "desconocido", false],
      [fmtInt(s.input_tokens), true],
      [fmtInt(s.output_tokens), true],
      [fmtInt(s.message_count), true],
      [calc ? fmtMoney(s.cost.total_cost, r.currency) : "—", true],
    ];
    for (const [val, num] of cells) {
      const td = el("td", num ? "num" : null, val);
      tr.appendChild(td);
    }
    const tdStatus = el("td");
    const status = s.cost ? s.cost.status : "tokens_faltantes";
    const span = el(
      "span",
      `status ${calc ? "calculado" : "no-calc"}`,
      calc ? "calculado" : status
    );
    tdStatus.appendChild(span);
    tr.appendChild(tdStatus);
    tbody.appendChild(tr);
  }
}

function renderDiscovery(r) {
  const root = document.getElementById("discovery");
  const d = r.discovery || {};
  root.innerHTML = "";
  const entries = Object.values(d);
  if (!entries.length) {
    root.appendChild(el("div", "label", "Discovery no ejecutado."));
    return;
  }
  for (const tool of entries) {
    const item = el("div", "disc-item");
    const status = tool.detected ? "detectado" : "no detectado";
    let txt = `${tool.tool}: ${status}`;
    if (tool.skills_installed && tool.skills_installed.length)
      txt += ` — Skills: ${tool.skills_installed.join(", ")}`;
    if (tool.paths_read && tool.paths_read.length)
      txt += ` — rutas: ${tool.paths_read.join(", ")}`;
    item.appendChild(el("div", null, txt));
    if (tool.cost_note) item.appendChild(el("div", "label", tool.cost_note));
    root.appendChild(item);
  }
}

function renderWarnings(r) {
  const root = document.getElementById("warnings");
  root.innerHTML = "";
  if (!r.warnings.length) {
    root.appendChild(el("li", null, "Sin advertencias."));
    return;
  }
  for (const w of r.warnings) {
    root.appendChild(el("li", null, `[${w.type}] ${w.message}${w.source ? " — " + w.source : ""}`));
  }
}

async function main() {
  const res = await fetch("./api/report");
  const r = await res.json();
  document.getElementById("disclaimer").textContent = r.disclaimer;
  document.getElementById("generated").textContent = r.generated_at
    ? `Generado: ${r.generated_at}`
    : "";
  renderKpis(r);
  renderIntegrity(r);
  renderBars("by-day", r.by_day, "day", "total_cost", r.currency);
  renderBars("by-model", r.by_model, "model", "total_cost", r.currency);
  renderSessions(r);
  renderDiscovery(r);
  renderWarnings(r);
}

main().catch((e) => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<pre style="color:#b91c1c;padding:1rem">Error cargando el reporte: ${e}</pre>`
  );
});

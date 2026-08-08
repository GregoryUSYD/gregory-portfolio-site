// Shared top-ticker loader for pages that don't render the full watchlist
// grids (Home / Research / About). watchlists.html has its own copy of this
// logic bundled with its grid-rendering script, so it isn't loaded here.
function buildTicker(items) {
  return items.map(item => {
    if (!item.ok) return `<span class="tk-name">${item.name}</span><span class="tk-sep">N/A</span>`;
    const cls = item.chg > 0 ? "tk-up" : item.chg < 0 ? "tk-down" : "";
    const sign = item.chg > 0 ? "+" : "";
    return `<span class="tk-name">${item.name}</span><span>${item.last}</span> <span class="${cls}">${sign}${item.pct}%</span>`;
  }).join(' <span class="tk-sep">·</span> ');
}

async function loadTicker() {
  try {
    const res = await fetch("market_data.json", { cache: "no-store" });
    const data = await res.json();
    const tickerEl = document.getElementById("market-ticker");
    const joined = buildTicker(data.categories.indices || []) + ' <span class="tk-sep">·</span> ';
    tickerEl.innerHTML = `<span class="ticker-copy">${joined}</span><span class="ticker-copy" aria-hidden="true">${joined}</span>`;
  } catch (e) {
    console.error("Could not load ticker data.", e);
  }
}

loadTicker();
setInterval(loadTicker, 30000);

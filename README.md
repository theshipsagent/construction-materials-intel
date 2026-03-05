# Construction Materials Intelligence Report

Interactive HTML report covering the US construction materials supply chain:
cement, supplementary cementitious materials (slag, fly ash, natural pozzolans),
and the blast furnace steel mills that produce slag.

## What It Generates

A single standalone HTML file (`output/construction_materials_intelligence_report.html`)
with 10 sections, 15 Chart.js charts, and an interactive Leaflet.js map showing:
- 50 US cement plants (sized by capacity)
- 24 import ports (sized by volume)
- 8 US blast furnace / integrated steel mills (live from AIST data)
- 8 natural pozzolan deposits

Dark/light mode toggle. Open in any browser — no server required.

## Data Sources

| Data | Source | File |
|---|---|---|
| Cement & slag production stats (2020–2024) | USGS Mineral Commodity Summaries | `data/usgs_minerals.duckdb` |
| Blast furnace mill locations | AIST Steel Mill Directory | `data/facilities_steel_mill.geojson` |
| Cement plants, import ports, pozzolan deposits | PCA / industry curated | hardcoded in `build_report.py` |

The `usgs_minerals.duckdb` database contains 32,344 parsed MCS stat records across
37 mineral commodities — production, imports, exports, price, and net import reliance
by year. It was built by scraping and parsing USGS MCS annual PDFs.

## Setup

```bash
pip install -r requirements.txt
python build_report.py
```

Output: `output/construction_materials_intelligence_report.html`

Open the file in a browser. Internet connection required for map tiles and CDN assets
(Chart.js, Leaflet.js, Google Fonts). All data is embedded inline — no server needed.

## Requirements

- Python 3.11+
- duckdb >= 0.9.0

## Tech Stack

- Chart.js 4.4.0
- Leaflet.js 1.9.4 + CartoDB DarkMatter tiles
- Space Grotesk font (Google Fonts CDN)
- No frontend build step

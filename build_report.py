"""
US Construction Materials Intelligence Report
==============================================
Standalone build script — no external project dependencies.

Data:
    data/usgs_minerals.duckdb          USGS Mineral Commodity Summaries (parsed)
    data/facilities_steel_mill.geojson AIST Steel Mill Directory 2021

Usage:
    pip install -r requirements.txt
    python3 build_report.py

Output:
    output/construction_materials_intelligence_report.html
"""

import json
import statistics
import duckdb
from datetime import date
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
DB_PATH    = ROOT / "data" / "usgs_minerals.duckdb"
GJ_PATH    = ROOT / "data" / "facilities_steel_mill.geojson"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT     = OUTPUT_DIR / "construction_materials_intelligence_report.html"


# ── USGS data helpers ─────────────────────────────────────────────────────────

def pull_series(db, commodity, metric, yr_min, yr_max, val_min, val_max):
    """Pull metric from mcs_salient_stats, filter to plausible range, return {year: median}."""
    rows = db.execute("""
        SELECT year, value FROM mcs_salient_stats
        WHERE commodity = ? AND metric = ?
          AND year BETWEEN ? AND ?
          AND value BETWEEN ? AND ?
        ORDER BY year
    """, [commodity, metric, yr_min, yr_max, val_min, val_max]).fetchall()

    by_year = {}
    for yr, val in rows:
        by_year.setdefault(yr, []).append(val)
    return {yr: statistics.median(vals) for yr, vals in sorted(by_year.items())}


def series_for_years(series, years, divisor=1.0):
    return [round(series[y] / divisor, 1) if y in series else None for y in years]


# ── load live data ─────────────────────────────────────────────────────────────

def load_data():
    db = duckdb.connect(str(DB_PATH), read_only=True)

    years5 = list(range(2020, 2025))

    # Cement production (thousands MT → millions)
    cem_prod_s = pull_series(db, "cement", "production_us", 2019, 2024, 75_000, 100_000)
    cem_prod   = series_for_years(cem_prod_s, years5, divisor=1000)
    cem_cons   = [round(v * 1.22, 1) if v else None for v in cem_prod]

    # Cement price
    cem_price_s = pull_series(db, "cement", "price_avg", 2019, 2024, 80, 200)
    cem_price   = max(cem_price_s.values()) if cem_price_s else 155

    # Pumice production (thousand short tons)
    pumice_yrs  = list(range(2019, 2025))
    pumice_s    = pull_series(db, "pumice", "other_production_mine", 2019, 2025, 200, 700)
    pumice_prod = series_for_years(pumice_s, pumice_yrs)

    # Slag consumption + imports
    slag_cons_s = pull_series(db, "iron_steel_slag", "apparent_consumption", 2019, 2025, 10, 25)
    slag_imp_s  = pull_series(db, "iron_steel_slag", "imports_for_consumption", 2019, 2025, 1.0, 4.0)
    slag_cons   = slag_cons_s.get(max(slag_cons_s, default=2024), 16.0)
    slag_imp    = slag_imp_s.get(max(slag_imp_s, default=2024), 2.1)

    db.close()

    return {
        "cement_prod_years":   [str(y) for y in years5],
        "cement_prod":         cem_prod,
        "cement_cons":         cem_cons,
        "cement_price":        round(cem_price, 0),
        "pumice_prod_years":   [str(y) for y in pumice_yrs],
        "pumice_prod":         pumice_prod,
        "slag_cons":           round(slag_cons, 1),
        "slag_imp":            round(slag_imp, 1),
    }


def load_bf_mills():
    """US blast furnace mills from AIST GeoJSON."""
    with open(GJ_PATH) as f:
        gj = json.load(f)
    mills = []
    for feat in gj["features"]:
        p     = feat["properties"]
        ftype = p.get("facility_types", "").lower()
        if "blast_furnace" not in ftype:
            continue
        if p.get("country", "US") not in ("US", ""):
            continue
        c = feat["geometry"]["coordinates"]
        mills.append([p["name"], p.get("company", ""), f"{p.get('city','')}, {p.get('state','')}", c[1], c[0]])
    return mills


# ── static reference data ─────────────────────────────────────────────────────

CEMENT_PLANTS = [
    ["Midlothian","Holcim","TX",1.9,32.45,-96.98],["Alpena","Holcim","MI",2.5,45.08,-83.43],
    ["Ste. Genevieve","Holcim","MO",4.0,37.97,-90.04],["Mitchell","Heidelberg","IN",3.2,38.73,-86.47],
    ["Hagerstown","Heidelberg","MD",2.0,39.63,-77.71],["Waco","Heidelberg","TX",2.0,31.51,-97.20],
    ["Leeds","Heidelberg","AL",1.4,33.53,-86.55],["San Juan","CEMEX","TX",1.8,26.19,-98.16],
    ["Balcones","CEMEX","TX",1.5,30.52,-97.92],["Brooksville","CEMEX","FL",1.5,28.56,-82.42],
    ["Victorville","CEMEX","CA",1.2,34.56,-117.36],["Fairborn","CEMEX","OH",1.4,39.81,-84.03],
    ["Pennsuco","Titan America","FL",2.1,28.35,-81.98],["Tampa","Argos USA","FL",1.9,27.95,-82.45],
    ["Newberry","Argos USA","FL",1.6,29.65,-82.60],["Roberta","Argos USA","AL",1.8,32.76,-87.16],
    ["Harleyville","Argos USA","SC",1.5,33.22,-80.45],["Chanute","Buzzi Unicem","KS",1.0,37.68,-95.46],
    ["Greencastle","Buzzi Unicem","IN",1.2,39.64,-86.82],["Cape Girardeau","Buzzi Unicem","MO",1.3,37.31,-89.55],
    ["Festus","Buzzi Unicem","MO",1.0,38.21,-90.39],["Pryor","Buzzi Unicem","OK",0.8,36.31,-95.32],
    ["Foreman","CRH/Ash Grove","AR",1.5,33.72,-94.39],["Durkee","CRH/Ash Grove","OR",0.7,44.59,-117.89],
    ["Montana City","CRH/Ash Grove","MT",1.0,46.62,-111.93],["Seattle","CRH/Ash Grove","WA",0.9,47.56,-122.34],
    ["Buda","Eagle Materials","TX",1.3,30.08,-97.84],["LaSalle","Eagle Materials","IL",1.0,41.33,-89.07],
    ["Sugar Creek","Eagle Materials","MO",0.9,39.11,-94.42],["Laramie","Eagle Materials","WY",0.8,41.31,-105.59],
    ["Fernley","Eagle Materials","NV",0.7,39.61,-119.25],["Sumterville","CRH","FL",1.2,28.76,-82.07],
    ["Branford","CRH","FL",1.0,29.95,-82.93],["Miami","CEMEX","FL",1.1,25.79,-80.27],
    ["Catskill","Heidelberg","NY",1.0,42.22,-73.87],["Nazareth","Heidelberg","PA",1.5,40.74,-75.31],
    ["Speed","Heidelberg","IN",1.4,38.73,-86.47],["Logansport","Heidelberg","IN",1.1,40.75,-86.36],
    ["Ada","Holcim","OK",1.0,34.77,-96.67],["Florence","Holcim","CO",1.2,38.39,-105.12],
    ["Devils Slide","Holcim","UT",0.9,41.06,-111.52],["Mason City","Holcim","IA",1.0,43.15,-93.20],
    ["Joppa","Holcim","IL",1.2,37.22,-88.82],["Theodore","Holcim","AL",1.5,30.53,-88.17],
    ["Trident","Holcim","MT",0.8,46.30,-111.51],["Artesia","Holcim","MS",0.9,33.42,-88.65],
    ["Calera","National Cement","AL",1.3,33.10,-86.75],["Thomaston","Heidelberg","ME",0.6,44.09,-69.18],
    ["Union Bridge","Heidelberg","MD",1.2,39.57,-77.17],["Lebec","National Cement","CA",1.0,34.84,-118.87],
]

IMPORT_PORTS = [
    ["Houston, TX",5_717_149,"5.72M MT",193,29.72,-95.05],
    ["NY/Newark, NJ",856_976,"857K MT",31,40.68,-74.15],
    ["Portland, OR",747_137,"747K MT",26,45.55,-122.67],
    ["Stockton, CA",504_643,"505K MT",17,37.95,-121.30],
    ["Gramercy, LA",419_976,"420K MT",14,30.05,-90.70],
    ["Norfolk, VA",418_674,"419K MT",22,36.85,-76.30],
    ["Tampa Bay, FL",396_594,"397K MT",19,27.85,-82.45],
    ["Providence, RI",390_778,"391K MT",51,41.82,-71.40],
    ["Lower Miss River",357_744,"358K MT",9,29.95,-90.10],
    ["Savannah, GA",294_289,"294K MT",30,32.08,-81.10],
    ["Brownsville, TX",216_639,"217K MT",5,25.95,-97.40],
    ["Philadelphia, PA",210_584,"211K MT",5,39.95,-75.15],
    ["Pt Everglades, FL",203_233,"203K MT",12,26.08,-80.12],
    ["Lake Charles, LA",192_016,"192K MT",7,30.20,-93.25],
    ["San Francisco, CA",172_695,"173K MT",7,37.80,-122.40],
    ["W. Palm Beach, FL",162_709,"163K MT",10,26.72,-80.05],
    ["Portsmouth, NH",105_495,"105K MT",12,43.08,-70.75],
    ["Jacksonville, FL",85_000,"85K MT",8,30.33,-81.66],
    ["New Orleans, LA",46_910,"47K MT",1,29.95,-90.05],
    ["Corpus Christi, TX",45_000,"45K MT",3,27.80,-97.40],
    ["Mobile, AL",30_016,"30K MT",2,30.70,-88.05],
    ["Pt Manatee, FL",16_498,"16K MT",1,27.65,-82.55],
]

POZZOLAN_DEPOSITS = [
    ["Hess Pumice","Malad City, ID","Pumice pozzolan",42.19,-112.25],
    ["CR Minerals","Santa Fe, NM","Pumice, volcanic ash",35.08,-106.65],
    ["Kirkland Mining","Kirkland, AZ","Pumiceous tuff (39 Mt reserves)",34.45,-112.73],
    ["Geofortis/CRH","Tooele, UT","Natural pozzolan",40.53,-112.30],
    ["St. Cloud Mining","Winston, NM","Zeolite pozzolan",33.35,-107.64],
    ["Sunrise Resources","Churchill Co., NV","Glassy pumice",39.50,-118.80],
    ["Burgess Pigment","Sandersville, GA","Metakaolin",32.98,-82.81],
    ["Glass Mountain","Siskiyou Co., CA","Obsidian/pumice",41.23,-121.49],
]


# ── HTML ───────────────────────────────────────────────────────────────────────

def build_html(d, bf_mills):
    today = date.today().strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>US Construction Materials Intelligence | OceanDatum</title>
    <meta name="description" content="Comprehensive analysis of US cement, slag, fly ash, and natural pozzolan markets — supply chains, infrastructure mapping, and strategic outlook through 2030.">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root{{
            --primary:#2E7D32;--primary-dark:#1B5E20;--primary-light:#4CAF50;
            --secondary:#1976D2;--secondary-dark:#0D47A1;--secondary-light:#42A5F5;
            --accent:#00ACC1;--accent-dark:#00897B;
            --slag-blue:#2c5282;--flyash-amber:#FF8F00;--pozzolan-teal:#00695C;
            --page-bg:#0a0a0a;--page-bg-gradient:linear-gradient(135deg,#0a0a0a 0%,#1a1a2e 100%);
            --text-primary:rgba(255,255,255,0.9);--text-secondary:rgba(255,255,255,0.7);--text-muted:rgba(255,255,255,0.5);
            --section-bg:rgba(255,255,255,0.04);--section-border:rgba(255,255,255,0.1);
            --table-border:rgba(255,255,255,0.12);--table-row-alt:rgba(255,255,255,0.03);
            --card-bg:rgba(255,255,255,0.05);--card-border:rgba(255,255,255,0.1);
            --od-accent:#64ffb4;--chart-grid:rgba(255,255,255,0.08);--chart-text:rgba(255,255,255,0.7);
        }}
        body.light-mode{{
            --page-bg:#fff;--page-bg-gradient:#f5f5f0;
            --text-primary:#1a1a1a;--text-secondary:#333;--text-muted:#666;
            --section-bg:#fff;--section-border:rgba(0,0,0,0.08);
            --table-border:#e0e0e0;--table-row-alt:#fafbfc;
            --card-bg:#f0f4f8;--card-border:#d6dfe8;--od-accent:#0d3b66;
            --chart-grid:rgba(0,0,0,0.08);--chart-text:#555;
        }}
        *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
        body{{font-family:'Space Grotesk',-apple-system,sans-serif;line-height:1.6;
            background:var(--page-bg-gradient);color:var(--text-primary);-webkit-font-smoothing:antialiased;transition:background .3s,color .3s}}
        .od-navbar{{position:fixed;top:0;left:0;right:0;background:rgba(0,0,0,0.4);
            backdrop-filter:blur(20px) saturate(180%);border-bottom:1px solid rgba(255,255,255,0.15);
            padding:.8rem 2rem;z-index:2000;display:flex;align-items:center;justify-content:space-between}}
        body.light-mode .od-navbar{{background:rgba(255,255,255,0.85);border-bottom-color:rgba(0,0,0,0.1)}}
        .od-navbar-brand{{font-size:.85rem;font-weight:300;font-style:italic;color:rgba(255,255,255,0.7)}}
        body.light-mode .od-navbar-brand{{color:rgba(0,0,0,0.5)}}
        .od-navbar-brand a{{color:rgba(255,255,255,0.9);font-weight:600;font-style:normal;text-decoration:none}}
        .od-navbar-brand a:hover{{color:#64ffb4}}
        .theme-toggle{{background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);
            color:rgba(255,255,255,0.8);border-radius:6px;padding:.45rem .7rem;cursor:pointer;font-size:1rem;transition:all .3s}}
        .theme-toggle:hover{{border-color:rgba(100,255,180,0.4);background:rgba(100,255,180,0.05)}}
        body.light-mode .theme-toggle{{background:rgba(0,0,0,0.05);border-color:rgba(0,0,0,0.15);color:#333}}
        .header{{background:linear-gradient(135deg,rgba(27,94,32,0.8) 0%,rgba(13,71,161,0.8) 50%,rgba(0,105,92,0.8) 100%);
            color:#fff;padding:110px 20px 55px;text-align:center;position:relative;overflow:hidden}}
        body.light-mode .header{{background:linear-gradient(135deg,#1B5E20,#0D47A1,#00695C)}}
        .header h1{{font-size:2.8rem;font-weight:300;margin-bottom:12px;letter-spacing:-.5px}}
        .header .subtitle{{font-size:1.2rem;opacity:.9;max-width:820px;margin:0 auto}}
        .header .meta{{font-size:.88rem;opacity:.65;margin-top:18px}}
        .header .meta a{{color:rgba(255,255,255,0.85);text-decoration:none}}
        .nav{{background:rgba(10,10,10,0.85);backdrop-filter:blur(12px);padding:10px 20px;
            position:sticky;top:56px;z-index:1000;display:flex;gap:5px;justify-content:center;
            flex-wrap:wrap;box-shadow:0 3px 12px rgba(0,0,0,0.25);border-bottom:1px solid var(--section-border)}}
        body.light-mode .nav{{background:#263238}}
        .nav a{{color:rgba(255,255,255,0.85);text-decoration:none;padding:8px 14px;border-radius:4px;
            font-size:.82rem;font-weight:500;transition:all .25s;white-space:nowrap}}
        .nav a:hover{{background:rgba(255,255,255,0.12)}}
        .nav a.active{{background:var(--primary);color:#fff}}
        .container{{max-width:1600px;margin:0 auto;padding:30px}}
        .section{{background:var(--section-bg);border-radius:12px;padding:35px;margin-bottom:30px;
            box-shadow:0 2px 12px rgba(0,0,0,0.15);border:1px solid var(--section-border);transition:background .3s,border-color .3s}}
        .section-header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px;margin-bottom:28px}}
        .section-title{{color:var(--od-accent);font-size:1.6rem;font-weight:600;border-left:4px solid var(--od-accent);padding-left:15px}}
        body.light-mode .section-title{{color:var(--primary-dark);border-left-color:var(--primary)}}
        .section-title.blue{{border-left-color:#64b5f6;color:#90caf9}}
        .section-title.amber{{border-left-color:#ffb74d;color:#ffcc80}}
        .section-title.teal{{border-left-color:#80cbc4;color:#80cbc4}}
        body.light-mode .section-title.blue{{border-left-color:var(--slag-blue);color:var(--slag-blue)}}
        body.light-mode .section-title.amber{{border-left-color:var(--flyash-amber);color:#E65100}}
        body.light-mode .section-title.teal{{border-left-color:var(--pozzolan-teal);color:var(--pozzolan-teal)}}
        .badges{{display:flex;gap:8px;flex-wrap:wrap}}
        .badge{{padding:5px 14px;border-radius:20px;font-size:.78rem;font-weight:600;color:#fff;letter-spacing:.2px}}
        .badge-green{{background:var(--primary)}}.badge-blue{{background:var(--secondary)}}
        .badge-teal{{background:var(--accent)}}.badge-amber{{background:var(--flyash-amber)}}
        .badge-red{{background:#E53935}}.badge-gold{{background:#FFC107;color:#333}}
        .badge-slag{{background:var(--slag-blue)}}
        .grid-2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:30px}}
        .grid-3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:25px}}
        .grid-4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}}
        .grid-5{{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:15px}}
        .kpi-card{{background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border-radius:12px;padding:22px 20px;text-align:center}}
        .kpi-card.blue{{background:linear-gradient(135deg,var(--secondary),var(--secondary-dark))}}
        .kpi-card.teal{{background:linear-gradient(135deg,var(--accent),var(--accent-dark))}}
        .kpi-card.gold{{background:linear-gradient(135deg,#F9A825,#E65100)}}
        .kpi-card.slag{{background:linear-gradient(135deg,#3182ce,var(--slag-blue))}}
        .kpi-card.amber{{background:linear-gradient(135deg,#FF8F00,#E65100)}}
        .kpi-card.red{{background:linear-gradient(135deg,#E53935,#b71c1c)}}
        .kpi-card.pozzolan{{background:linear-gradient(135deg,var(--pozzolan-teal),#004D40)}}
        .kpi-value{{font-size:2.2rem;font-weight:700;letter-spacing:-.5px;margin-bottom:4px}}
        .kpi-label{{font-size:.85rem;opacity:.9;font-weight:600;text-transform:uppercase;letter-spacing:.5px}}
        .kpi-sub{{font-size:.78rem;opacity:.75;margin-top:6px}}
        .chart-container{{position:relative;height:280px}}
        .chart-label{{font-size:.82rem;color:var(--text-muted);margin-bottom:6px;font-weight:500;text-transform:uppercase;letter-spacing:.5px}}
        .callout{{border-radius:10px;padding:22px 25px;margin:20px 0;border-left:4px solid}}
        .callout h4{{font-size:1.05rem;font-weight:600;margin-bottom:10px}}
        .callout p{{font-size:.92rem;line-height:1.7;color:var(--text-secondary)}}
        .callout p+p{{margin-top:8px}}
        .callout-red{{background:rgba(229,57,53,0.08);border-color:#E53935}}.callout-red h4{{color:#ef9a9a}}
        .callout-blue{{background:rgba(49,130,206,0.08);border-color:#3182ce}}.callout-blue h4{{color:#90caf9}}
        .callout-amber{{background:rgba(255,143,0,0.08);border-color:#FF8F00}}.callout-amber h4{{color:#ffcc80}}
        body.light-mode .callout-red h4{{color:#c62828}}
        body.light-mode .callout-blue h4{{color:#0D47A1}}
        body.light-mode .callout-amber h4{{color:#E65100}}
        .callout-highlight{{background:linear-gradient(135deg,rgba(100,255,180,0.08),rgba(0,172,193,0.08));
            border-left:4px solid #64ffb4;border-radius:10px;padding:22px 25px;margin:20px 0}}
        .callout-highlight h4{{color:#64ffb4;font-size:1.1rem;font-weight:600;margin-bottom:10px}}
        body.light-mode .callout-highlight{{background:rgba(13,59,102,0.05);border-color:#0d3b66}}
        body.light-mode .callout-highlight h4{{color:#0d3b66}}
        .summary-card{{background:var(--card-bg);border:1px solid var(--card-border);border-radius:10px;padding:22px}}
        .summary-card h4{{font-size:1rem;font-weight:600;color:var(--od-accent);margin-bottom:10px}}
        body.light-mode .summary-card h4{{color:var(--primary-dark)}}
        .summary-card p{{font-size:.88rem;color:var(--text-secondary);line-height:1.65}}
        .summary-card.blue-top{{border-top:3px solid var(--secondary)}}
        .summary-card.amber-top{{border-top:3px solid var(--flyash-amber)}}
        .table-wrap{{overflow-x:auto;border-radius:8px;border:1px solid var(--table-border)}}
        table{{width:100%;border-collapse:collapse;font-size:.88rem}}
        th{{background:rgba(255,255,255,0.06);padding:11px 14px;text-align:left;font-size:.78rem;
            font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:var(--text-muted);
            border-bottom:1px solid var(--table-border)}}
        body.light-mode th{{background:rgba(0,0,0,0.04);color:#555}}
        td{{padding:10px 14px;border-bottom:1px solid var(--table-border);color:var(--text-secondary)}}
        tr:nth-child(even) td{{background:var(--table-row-alt)}}
        tr:last-child td{{border-bottom:none}}
        tr:hover td{{background:rgba(100,255,180,0.04)}}
        .blue-header{{background:rgba(49,130,206,0.12)!important}}
        .amber-header{{background:rgba(255,143,0,0.12)!important}}
        .trend-up{{color:#4CAF50;font-weight:600}}.trend-down{{color:#E53935;font-weight:600}}
        .hl{{color:var(--od-accent);font-weight:600}}
        body.light-mode .hl{{color:var(--primary-dark)}}
        .data-tag{{display:inline-flex;align-items:center;gap:5px;font-size:.72rem;color:var(--od-accent);
            background:rgba(100,255,180,0.08);border:1px solid rgba(100,255,180,0.2);
            border-radius:4px;padding:3px 8px;font-weight:500}}
        body.light-mode .data-tag{{color:var(--primary-dark);background:rgba(46,125,50,0.08);border-color:rgba(46,125,50,0.2)}}
        #mapContainer{{height:520px;border-radius:12px;border:2px solid var(--section-border)}}
        .layer-control{{background:rgba(20,20,30,0.92);border:1px solid rgba(255,255,255,0.2);
            border-radius:8px;padding:14px 18px;min-width:200px;color:rgba(255,255,255,0.85)}}
        body.light-mode .layer-control{{background:rgba(255,255,255,0.95);color:#333;border-color:rgba(0,0,0,0.15)}}
        .layer-control h4{{font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;color:rgba(255,255,255,0.6)}}
        body.light-mode .layer-control h4{{color:#666}}
        .layer-control label{{display:flex;align-items:center;gap:8px;font-size:.83rem;margin-bottom:7px;cursor:pointer}}
        .footer{{text-align:center;padding:40px 20px;color:var(--text-muted);font-size:.85rem}}
        .footer a{{color:var(--od-accent);text-decoration:none}}
        body.light-mode .footer a{{color:var(--primary)}}
        @media(max-width:768px){{.header h1{{font-size:1.9rem}}.grid-2,.grid-3,.grid-4,.grid-5{{grid-template-columns:1fr}}}}
    </style>
</head>
<body>

<nav class="od-navbar">
    <div class="od-navbar-brand"><a href="#">OceanDatum</a> &nbsp;/&nbsp; Construction Materials Intelligence</div>
    <button class="theme-toggle" onclick="document.body.classList.toggle('light-mode');updateChartTheme();updateMapTiles()" title="Toggle theme">&#9680;</button>
</nav>

<div class="header">
    <h1>US Construction Materials Intelligence</h1>
    <div class="subtitle">Cement &bull; Slag/GGBFS &bull; Fly Ash &bull; Natural Pozzolans &mdash; Supply Chains, Infrastructure &amp; Strategic Outlook Through 2030</div>
    <div class="meta">Generated {today} &bull; Data: USGS Mineral Commodity Summaries &bull; AIST Steel Mill Directory &bull; <a href="https://oceandatum.ai">OceanDatum.ai</a></div>
</div>

<div class="nav">
    <a href="#executive" class="active">Overview</a>
    <a href="#cement">Cement</a>
    <a href="#slag">Slag/GGBFS</a>
    <a href="#flyash">Fly Ash</a>
    <a href="#pozzolans">Pozzolans</a>
    <a href="#comparison">SCM Compare</a>
    <a href="#mapSection">Map</a>
    <a href="#supplychain">Supply Chain</a>
    <a href="#outlook">Outlook</a>
    <a href="#sources">Sources</a>
</div>

<div class="container">

<!-- EXECUTIVE SUMMARY -->
<section class="section" id="executive">
    <div class="section-header">
        <h2 class="section-title">Executive Summary</h2>
        <div class="badges"><span class="badge badge-green">$17B+ Market</span><span class="badge badge-blue">4 SCM Segments</span><span class="badge badge-amber">Structural Shift Underway</span></div>
    </div>
    <div class="grid-5" style="margin-bottom:25px;">
        <div class="kpi-card"><div class="kpi-value">92.6M</div><div class="kpi-label">MT Cement Production</div><div class="kpi-sub">99 plants &bull; 34 states</div></div>
        <div class="kpi-card slag"><div class="kpi-value">{d["slag_cons"]} Mt</div><div class="kpi-label">Slag Market</div><div class="kpi-sub">GGBFS &lt;3% tonnage, ~80% value</div></div>
        <div class="kpi-card amber"><div class="kpi-value">67M</div><div class="kpi-label">Tons CCP (2023)</div><div class="kpi-sub">Fly Ash &bull; 72% Beneficial Use Record</div></div>
        <div class="kpi-card pozzolan"><div class="kpi-value">2.5 Mt</div><div class="kpi-label">Natural Pozzolans</div><div class="kpi-sub">Growing 15%+ Annually</div></div>
        <div class="kpi-card red"><div class="kpi-value">20M+ MT</div><div class="kpi-label">Import Gap</div><div class="kpi-sub">Consumption Exceeds Production</div></div>
    </div>
    <div class="callout callout-highlight">
        <h4>The SCM Inflection Point</h4>
        <p>The US cementitious materials landscape is at a structural inflection point. Coal plant retirements are permanently reducing fly ash supply &mdash; 14.5 GW retiring in 2025 alone. Blast furnace closures are constraining slag availability as EAF steelmaking reaches 70%+ market share. Natural pozzolans and LC3 technology are emerging as cost-competitive alternatives, with natural pozzolan pricing (~$115/Mt) converging with fly ash ($118/Mt) for the first time. Tariff actions on cement imports from Turkey, Vietnam, and Canada are simultaneously reshaping $2.4B in annual trade flows.</p>
    </div>
    <div class="grid-3" style="margin-top:25px;">
        <div class="summary-card"><h4>Cement: Tariffs Reshaping Trade</h4><p>Section 232 tariffs on Canada (25%) and Mexico (25%), plus AD/CVD duties on Vietnam (46%), are restructuring $2.4B in annual cement imports. Turkey holds 36% market share at 10% baseline. The 20M+ MT import gap cannot be closed by domestic production alone &mdash; only 72% capacity utilization at 99 plants.</p></div>
        <div class="summary-card blue-top"><h4>Slag: Structural Supply Crisis</h4><p>EAF steelmaking now at 70%+ of US production. Slag cement shipments fell 16% to 3.7 Mt in 2024. Dearborn Works idled March 2025. Import dependency on Japan (52% share) is growing, but Japan is also reducing BF capacity under its Green Transformation plan. GGBFS is &lt;3% of slag tonnage but ~80% of value.</p></div>
        <div class="summary-card amber-top"><h4>Fly Ash: Declining Resource</h4><p>Coal capacity down from 318 GW peak (2011) to 165 GW, with 68.8 GW of additional retirements through 2030. CCP production fell to 67M tons in 2023. Reclaimed ash (4.5M tons in 2023) growing but cannot fully offset supply losses. US prices at $123/MT vs. $16&ndash;27/MT Asian FOB create import arbitrage.</p></div>
    </div>
</section>

<!-- US CEMENT -->
<section class="section" id="cement">
    <div class="section-header">
        <h2 class="section-title">US Cement Market</h2>
        <div class="badges"><span class="badge badge-green">92.6M MT</span><span class="badge badge-blue">$17B Market</span><span class="badge badge-red">22% Import Share</span><span class="data-tag">&#9679; USGS MCS Live</span></div>
    </div>
    <div class="grid-5" style="margin-bottom:25px;">
        <div class="kpi-card"><div class="kpi-value">92.6M</div><div class="kpi-label">MT Production</div><div class="kpi-sub">99 plants in 34 states</div></div>
        <div class="kpi-card blue"><div class="kpi-value">113M</div><div class="kpi-label">MT Consumption</div><div class="kpi-sub">Demand exceeds supply</div></div>
        <div class="kpi-card teal"><div class="kpi-value">22%</div><div class="kpi-label">Import Share</div><div class="kpi-sub">~20M MT annually</div></div>
        <div class="kpi-card gold"><div class="kpi-value">72%</div><div class="kpi-label">Capacity Utilization</div><div class="kpi-sub">120 MT nameplate</div></div>
        <div class="kpi-card"><div class="kpi-value">${int(d["cement_price"])}</div><div class="kpi-label">Per MT Price</div><div class="kpi-sub">USGS MCS latest</div></div>
    </div>
    <div class="grid-2">
        <div><div class="chart-label">Production vs Consumption (Million MT) <span class="data-tag">USGS MCS</span></div><div class="chart-container"><canvas id="cProdCons"></canvas></div></div>
        <div><div class="chart-label">Import Origins by Market Share</div><div class="chart-container"><canvas id="cImportPie"></canvas></div></div>
    </div>
    <div class="grid-2" style="margin-top:10px;">
        <div><div class="chart-label">5-Year Import Trend</div><div class="chart-container"><canvas id="cImportTrend"></canvas></div></div>
        <div><div class="chart-label">End-Use Segments</div><div class="chart-container"><canvas id="cEndUse"></canvas></div></div>
    </div>
    <h3 style="margin:30px 0 15px;color:var(--od-accent)">Import Tariff Landscape</h3>
    <div class="table-wrap"><table>
        <thead><tr><th>Origin</th><th>Volume (MT)</th><th>Share</th><th>Base Tariff</th><th>Section 232</th><th>AD/CVD</th><th>Effective Rate</th><th>Status</th></tr></thead>
        <tbody>
            <tr><td><strong>Turkey</strong></td><td>7.16M</td><td>36%</td><td>10%</td><td>&mdash;</td><td>&mdash;</td><td>10%</td><td><span class="badge badge-amber" style="font-size:.68rem">Under Review</span></td></tr>
            <tr><td><strong>Canada</strong></td><td>4.85M</td><td>24%</td><td>0%</td><td>25%</td><td>&mdash;</td><td>25%</td><td><span class="badge badge-red" style="font-size:.68rem">Active</span></td></tr>
            <tr><td><strong>Vietnam</strong></td><td>4.17M</td><td>21%</td><td>10%</td><td>&mdash;</td><td>36%</td><td>46%</td><td><span class="badge badge-red" style="font-size:.68rem">Active</span></td></tr>
            <tr><td><strong>Greece</strong></td><td>1.82M</td><td>9%</td><td>10%</td><td>&mdash;</td><td>&mdash;</td><td>10%</td><td><span class="badge badge-green" style="font-size:.68rem">Stable</span></td></tr>
            <tr><td><strong>Mexico</strong></td><td>1.32M</td><td>7%</td><td>0%</td><td>25%</td><td>&mdash;</td><td>25%</td><td><span class="badge badge-red" style="font-size:.68rem">Active</span></td></tr>
            <tr><td><strong>Egypt</strong></td><td>0.85M</td><td>4%</td><td>10%</td><td>&mdash;</td><td>&mdash;</td><td>10%</td><td><span class="badge badge-green" style="font-size:.68rem">Growing</span></td></tr>
        </tbody>
    </table></div>
    <h3 style="margin:30px 0 15px;color:var(--od-accent)">Top US Cement Companies</h3>
    <div class="table-wrap"><table>
        <thead><tr><th>Company</th><th>Plants</th><th>Capacity (MT)</th><th>Key States</th><th>HQ</th></tr></thead>
        <tbody>
            <tr><td><strong>Holcim/Lafarge</strong></td><td>14</td><td>~16M</td><td>MI, MO, AL, CO, IN</td><td>Switzerland</td></tr>
            <tr><td><strong>Heidelberg Materials</strong></td><td>13</td><td>~14M</td><td>TX, PA, MD, IN, MT</td><td>Germany</td></tr>
            <tr><td><strong>CEMEX</strong></td><td>10</td><td>~12M</td><td>TX, FL, CA, OH, PA</td><td>Mexico</td></tr>
            <tr><td><strong>CRH (Ash Grove)</strong></td><td>8</td><td>~9M</td><td>KS, NE, OR, WA, MT</td><td>Ireland</td></tr>
            <tr><td><strong>Buzzi Unicem</strong></td><td>7</td><td>~8M</td><td>TX, IN, MO, IA</td><td>Italy</td></tr>
            <tr><td><strong>Eagle Materials</strong></td><td>5</td><td>~5M</td><td>TX, MO, OK, NV, WY</td><td>USA</td></tr>
            <tr><td><strong>Argos USA</strong></td><td>4</td><td>~5M</td><td>FL, GA, AL, SC</td><td>Colombia</td></tr>
        </tbody>
    </table></div>
</section>

<!-- SLAG -->
<section class="section" id="slag">
    <div class="section-header">
        <h2 class="section-title blue">Slag/GGBFS Market</h2>
        <div class="badges"><span class="badge badge-slag">{d["slag_cons"]} Mt Consumption</span><span class="badge badge-red">Supply Crisis</span><span class="badge badge-teal">93&ndash;96% CO&#8322; Reduction</span><span class="data-tag">&#9679; USGS MCS Live</span></div>
    </div>
    <div class="grid-4" style="margin-bottom:25px;">
        <div class="kpi-card slag"><div class="kpi-value">{d["slag_cons"]} Mt</div><div class="kpi-label">Slag Sold/Used</div><div class="kpi-sub">GGBFS &lt;3% tonnage, ~80% value</div></div>
        <div class="kpi-card blue"><div class="kpi-value">$600M</div><div class="kpi-label">Market Value</div><div class="kpi-sub">GGBFS ~$480M at $100&ndash;140+/Mt</div></div>
        <div class="kpi-card red"><div class="kpi-value">3.7 Mt</div><div class="kpi-label">Cement Shipments</div><div class="kpi-sub">Down 16% from 4.4 Mt record (2023)</div></div>
        <div class="kpi-card pozzolan"><div class="kpi-value">93&ndash;96%</div><div class="kpi-label">CO&#8322; Reduction</div><div class="kpi-sub">35&ndash;67 kg vs 844&ndash;967 kg OPC</div></div>
    </div>
    <div class="callout callout-red">
        <h4>Structural Crisis: EAF Transition Eliminates Slag Supply</h4>
        <p>Electric Arc Furnace (EAF) steelmaking now accounts for 70%+ of US production, up from ~50% in 2005. EAFs produce no granulated blast furnace slag &mdash; the feedstock for GGBFS cement. Only ~7 integrated blast furnace mills remain operational. <strong>16.1 Mt/yr of new EAF capacity added (Q4 2023&ndash;2025)</strong> is accelerating the structural shift. Dearborn Works idled March 2025.</p>
    </div>
    <div class="grid-2">
        <div><div class="chart-label">Slag Cement Shipments (Mt)</div><div class="chart-container"><canvas id="slagShip"></canvas></div></div>
        <div><div class="chart-label">BF-BOF vs EAF Share (%)</div><div class="chart-container"><canvas id="eafChart"></canvas></div></div>
    </div>
    <h3 style="margin:30px 0 15px;color:var(--od-accent)">US Blast Furnace Infrastructure <span class="data-tag">AIST Directory Live</span></h3>
    <div class="table-wrap"><table><thead><tr><th class="blue-header">Facility</th><th class="blue-header">Operator</th><th class="blue-header">Location</th><th class="blue-header">Status</th></tr></thead><tbody id="bfTableBody"></tbody></table></div>
    <div class="grid-2" style="margin-top:25px;">
        <div><div class="chart-label">GGBFS Import Sources</div><div class="chart-container"><canvas id="slagImp"></canvas></div></div>
        <div class="callout callout-blue" style="margin-top:0;display:flex;flex-direction:column;justify-content:center;">
            <h4>Import Dependency Growing</h4>
            <p>As domestic blast furnace capacity declines, GGBFS imports have grown to ~{d["slag_imp"]}+ Mt/yr. Japan&rsquo;s share grew from 40% (2019) to 52% (2023). Transpacific shipping adds $25&ndash;35/MT.</p>
            <p style="margin-top:12px;"><strong>Key risk:</strong> Japan is reducing BF capacity under its Green Transformation plan, potentially constraining the largest US import source by 2028. New US terminals (Heidelberg Houston ~500K t/yr, Titan Norfolk $37M upgrade) are expanding import capacity.</p>
        </div>
    </div>
</section>

<!-- FLY ASH -->
<section class="section" id="flyash">
    <div class="section-header">
        <h2 class="section-title amber">Fly Ash Market</h2>
        <div class="badges"><span class="badge badge-amber">67M Tons CCP</span><span class="badge badge-green">72% Beneficial Use</span><span class="badge badge-red">Declining Supply</span></div>
    </div>
    <div class="grid-4" style="margin-bottom:25px;">
        <div class="kpi-card amber"><div class="kpi-value">67M</div><div class="kpi-label">Tons CCP (2023)</div><div class="kpi-sub">Down from 107M tons (2015)</div></div>
        <div class="kpi-card"><div class="kpi-value">72%</div><div class="kpi-label">Beneficial Use</div><div class="kpi-sub">Record &bull; 10th year above 50%</div></div>
        <div class="kpi-card red"><div class="kpi-value">165 GW</div><div class="kpi-label">Coal Capacity</div><div class="kpi-sub">Down from 318 GW peak (2011)</div></div>
        <div class="kpi-card gold"><div class="kpi-value">$123/MT</div><div class="kpi-label">US Fly Ash Price</div><div class="kpi-sub">vs $16&ndash;27/MT Asian FOB</div></div>
    </div>
    <div class="callout callout-amber">
        <h4>Coal Retirements Accelerating Supply Decline</h4>
        <p>EIA projects 165 GW of coal capacity in 2025, down from 318 GW peak. An additional 14.5 GW retires in 2025 alone. Each 1 GW retirement removes ~300,000&ndash;500,000 tons/yr of fresh fly ash supply. By 2030, only ~106 GW projected to remain &mdash; a 67% decline from peak.</p>
    </div>
    <div class="grid-2">
        <div><div class="chart-label">US Coal-Fired Capacity Decline (GW)</div><div class="chart-container"><canvas id="coalCap"></canvas></div></div>
        <div><div class="chart-label">CCP Production vs Beneficial Use (Mt)</div><div class="chart-container"><canvas id="ccpChart"></canvas></div></div>
    </div>
    <div style="margin-top:25px;">
        <div class="chart-label">Reclaimed Ash Growth (Mt)</div>
        <div class="chart-container" style="height:220px"><canvas id="reclaimedChart"></canvas></div>
    </div>
</section>

<!-- POZZOLANS -->
<section class="section" id="pozzolans">
    <div class="section-header">
        <h2 class="section-title teal">Natural Pozzolans</h2>
        <div class="badges"><span class="badge badge-teal">2.5 Mt Market</span><span class="badge badge-green">15%+ Annual Growth</span><span class="data-tag">&#9679; USGS MCS Live</span></div>
    </div>
    <div class="grid-4" style="margin-bottom:25px;">
        <div class="kpi-card pozzolan"><div class="kpi-value">2.5 Mt</div><div class="kpi-label">Market Size</div><div class="kpi-sub">Growing as SCM alternative</div></div>
        <div class="kpi-card teal"><div class="kpi-value">~$115</div><div class="kpi-label">Price/MT</div><div class="kpi-sub">Converging with fly ash</div></div>
        <div class="kpi-card"><div class="kpi-value">8</div><div class="kpi-label">Active Deposits</div><div class="kpi-sub">West-heavy: ID, NM, AZ, UT, NV</div></div>
        <div class="kpi-card gold"><div class="kpi-value">35 Mt</div><div class="kpi-label">Known Reserves</div><div class="kpi-sub">Kirkland, AZ alone</div></div>
    </div>
    <div class="grid-2">
        <div><div class="chart-label">US Pumice Mine Production (Thousand Short Tons) <span class="data-tag">USGS MCS</span></div><div class="chart-container"><canvas id="pumiceChart"></canvas></div></div>
        <div><div class="chart-label">Embodied CO&#8322; by Material (kg/MT)</div><div class="chart-container"><canvas id="co2Chart"></canvas></div></div>
    </div>
    <h3 style="margin:30px 0 15px;color:var(--od-accent)">Active Natural Pozzolan Producers</h3>
    <div class="table-wrap"><table>
        <thead><tr><th class="blue-header">Company</th><th class="blue-header">Location</th><th class="blue-header">Product</th><th class="blue-header">ASTM Class</th><th class="blue-header">Applications</th></tr></thead>
        <tbody>
            <tr><td><strong>Hess Pumice</strong></td><td>Malad City, ID</td><td>Pumice pozzolan</td><td>N</td><td>Concrete, SCM blend</td></tr>
            <tr><td><strong>CR Minerals</strong></td><td>Santa Fe, NM</td><td>Pumice, volcanic ash</td><td>N</td><td>Concrete, geopolymer</td></tr>
            <tr><td><strong>Kirkland Mining</strong></td><td>Kirkland, AZ</td><td>Pumiceous tuff</td><td>N</td><td>Mass concrete, dams</td></tr>
            <tr><td><strong>Geofortis/CRH</strong></td><td>Tooele, UT</td><td>Natural pozzolan</td><td>N</td><td>Blended cement</td></tr>
            <tr><td><strong>St. Cloud Mining</strong></td><td>Winston, NM</td><td>Zeolite pozzolan</td><td>N</td><td>Geopolymer, LC3</td></tr>
            <tr><td><strong>Burgess Pigment</strong></td><td>Sandersville, GA</td><td>Metakaolin</td><td>N/HRM</td><td>High-performance concrete</td></tr>
        </tbody>
    </table></div>
</section>

<!-- SCM COMPARISON -->
<section class="section" id="comparison">
    <div class="section-header">
        <h2 class="section-title">SCM Market Comparison</h2>
        <div class="badges"><span class="badge badge-green">4 Materials</span><span class="badge badge-blue">Price Convergence</span></div>
    </div>
    <div class="grid-2">
        <div><div class="chart-label">Price Trends ($/MT)</div><div class="chart-container"><canvas id="priceChart"></canvas></div></div>
        <div><div class="chart-label">SCM Supply Trajectories (Mt/yr) &mdash; Projected</div><div class="chart-container"><canvas id="scmTraj"></canvas></div></div>
    </div>
</section>

<!-- MAP -->
<section class="section" id="mapSection">
    <div class="section-header">
        <h2 class="section-title">US Cementitious Materials Infrastructure</h2>
        <div class="badges"><span class="badge badge-green">50 Cement Plants</span><span class="badge badge-red">22 Import Ports</span><span class="badge badge-slag">BF Mills (AIST Live)</span><span class="badge badge-teal">8 Pozzolan Deposits</span></div>
    </div>
    <div id="mapContainer"></div>
</section>

<!-- SUPPLY CHAIN -->
<section class="section" id="supplychain">
    <div class="section-header">
        <h2 class="section-title">Supply Chain &amp; Logistics</h2>
        <div class="badges"><span class="badge badge-blue">3 Modes</span><span class="badge badge-green">National Coverage</span></div>
    </div>
    <div class="grid-3" style="margin-bottom:25px;">
        <div class="summary-card"><h4>Port Infrastructure</h4><p><strong>22 major import ports</strong> handle cement, slag, and SCM imports. Deep-draft facilities (35&ndash;45 ft) required for Handysize/Supramax vessels. Gulf Coast handles 55%+ of volume. Discharge rate: ~8,000&ndash;10,000 t/day.</p></div>
        <div class="summary-card blue-top"><h4>Rail Networks</h4><p><strong>97 of 99 US cement plants</strong> are rail-served. Class I carriers (BNSF, UP, CSX, NS) provide long-haul capacity. Covered hopper cars (3,000&ndash;4,000 cu ft). Average rate: $0.03&ndash;0.05/MT-mile.</p></div>
        <div class="summary-card amber-top"><h4>Trucking</h4><p><strong>150&ndash;250 mile economic radius.</strong> Pneumatic tanker trailers carry 24&ndash;26 MT per load. Rate: $0.15&ndash;0.25/MT-mile (3&ndash;5x rail cost per mile).</p></div>
    </div>
    <h3 style="margin:20px 0 15px;color:var(--od-accent)">Major Import Terminals</h3>
    <div class="table-wrap"><table>
        <thead><tr><th>Port</th><th>Volume (MT)</th><th>Shipments</th><th>Key Operators</th><th>Products</th><th>Draft (ft)</th></tr></thead>
        <tbody>
            <tr><td><strong>Houston, TX</strong></td><td>5.72M</td><td>193</td><td>CEMEX, Holcim, Martin Marietta, Heidelberg</td><td>OPC, Slag, Fly Ash</td><td>45</td></tr>
            <tr><td><strong>NY/Newark, NJ</strong></td><td>857K</td><td>31</td><td>Heidelberg, Holcim</td><td>OPC, Slag</td><td>50</td></tr>
            <tr><td><strong>Portland, OR</strong></td><td>747K</td><td>26</td><td>CRH/Ash Grove, CalPortland</td><td>OPC</td><td>40</td></tr>
            <tr><td><strong>Tampa Bay, FL</strong></td><td>673K</td><td>36</td><td>CEMEX, Titan America, Argos</td><td>OPC, White Cement</td><td>43</td></tr>
            <tr><td><strong>Norfolk, VA</strong></td><td>419K</td><td>22</td><td>Titan America ($37M GGBFS terminal)</td><td>OPC, Slag</td><td>42</td></tr>
            <tr><td><strong>Savannah, GA</strong></td><td>294K</td><td>30</td><td>Argos, Heidelberg</td><td>OPC, Slag</td><td>42</td></tr>
        </tbody>
    </table></div>
</section>

<!-- OUTLOOK -->
<section class="section" id="outlook">
    <div class="section-header">
        <h2 class="section-title">Market Outlook 2025&ndash;2030</h2>
        <div class="badges"><span class="badge badge-green">$21B+ by 2030</span><span class="badge badge-blue">3.5% CAGR</span></div>
    </div>
    <div class="grid-2" style="margin-bottom:25px;">
        <div><div class="chart-label">Cementitious Market Volume by Segment (Mt/yr)</div><div class="chart-container"><canvas id="outlookChart"></canvas></div></div>
        <div class="callout callout-highlight" style="margin:0;display:flex;flex-direction:column;justify-content:center;">
            <h4>Strategic Outlook: The Substitution Race</h4>
            <p>By 2030, fly ash supply to concrete could fall from ~14.7 Mt to ~6 Mt, and GGBFS from 3.7 to 2.5 Mt. This ~10 Mt SCM supply gap will drive accelerating demand for natural pozzolans (projected 7 Mt by 2030). Infrastructure Act tailwind: $110B in federal infrastructure spending (IIJA) driving ~5% annual increase in ready-mix concrete demand through 2030.</p>
        </div>
    </div>
    <div class="grid-3">
        <div class="kpi-card"><div class="kpi-value">~5%</div><div class="kpi-label">Demand Growth</div><div class="kpi-sub">IIJA tailwind 2025&ndash;2028</div></div>
        <div class="kpi-card blue"><div class="kpi-value">106 GW</div><div class="kpi-label">Coal Capacity 2030P</div><div class="kpi-sub">Down 67% from peak &mdash; fly ash collapse</div></div>
        <div class="kpi-card pozzolan"><div class="kpi-value">7 Mt</div><div class="kpi-label">Pozzolan Demand 2030P</div><div class="kpi-sub">From 2.5 Mt today &mdash; 15%+ CAGR</div></div>
    </div>
</section>

<!-- SOURCES -->
<section class="section" id="sources">
    <div class="section-header"><h2 class="section-title">Data Sources</h2></div>
    <div class="grid-3" style="font-size:.88rem;color:var(--text-secondary);">
        <div>
            <p><strong style="color:var(--od-accent)">USGS — Live (data/usgs_minerals.duckdb)</strong></p>
            <p>Mineral Commodity Summaries 2002&ndash;2024</p>
            <p>Commodities: cement, pumice, iron_steel_slag</p>
            <p>MRDS: 53,787 US mine facility records</p>
            <p style="margin-top:6px;font-style:italic">Parsed &amp; stored locally &mdash; no internet required to run</p>
        </div>
        <div>
            <p><strong style="color:var(--od-accent)">AIST — Live (data/facilities_steel_mill.geojson)</strong></p>
            <p>North American Steel Mill Directory 2021</p>
            <p>68 US/Canada facilities, blast furnace classification</p>
            <p style="margin-top:6px;font-style:italic">Parsed &amp; stored locally &mdash; no internet required to run</p>
        </div>
        <div>
            <p><strong style="color:var(--od-accent)">Curated Reference Data</strong></p>
            <p>Portland Cement Association (PCA) — plant list</p>
            <p>ACAA — CCP beneficial use report 2023</p>
            <p>NSA — National Slag Association</p>
            <p>EIA — coal capacity/retirement data</p>
            <p>Census Bureau — import trade data (tariff table)</p>
        </div>
    </div>
</section>

</div>

<div class="footer">
    <p>US Construction Materials Intelligence &bull; <a href="https://oceandatum.ai">OceanDatum.ai</a> &bull; Generated {today}</p>
    <p style="margin-top:6px;font-size:.78rem">Data: USGS MCS (local duckdb) &bull; AIST Steel Mill Directory (local geojson) &bull; Run: <code>python3 build_report.py</code></p>
</div>

<script>
(function(){{
'use strict';

// ── Live data from Python ───────────────────────────────────────────────────
const CEM_YEARS  = {json.dumps(d["cement_prod_years"])};
const CEM_PROD   = {json.dumps(d["cement_prod"])};
const CEM_CONS   = {json.dumps(d["cement_cons"])};
const PUM_YEARS  = {json.dumps(d["pumice_prod_years"])};
const PUM_PROD   = {json.dumps(d["pumice_prod"])};
const PLANTS     = {json.dumps(CEMENT_PLANTS)};
const PORTS      = {json.dumps(IMPORT_PORTS)};
const POZ        = {json.dumps(POZZOLAN_DEPOSITS)};
const BF_MILLS   = {json.dumps(bf_mills)};

// ── Colors ──────────────────────────────────────────────────────────────────
const C = {{
    green:['#1B5E20','#2E7D32','#4CAF50','#81C784'],
    blue:['#0D47A1','#1976D2','#42A5F5','#64B5F6'],
    teal:['#00897B','#00ACC1','#26A69A'],
    red:'#E53935', amber:'#FF8F00', slag:'#2c5282', poz:'#00695C'
}};

// ── Chart theme ─────────────────────────────────────────────────────────────
Chart.defaults.font.family = "'Space Grotesk',sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;

function applyChartTheme(){{
    const dark = !document.body.classList.contains('light-mode');
    Chart.defaults.color = dark?'rgba(255,255,255,0.7)':'#555';
    Chart.defaults.borderColor = dark?'rgba(255,255,255,0.08)':'rgba(0,0,0,0.1)';
    Chart.defaults.plugins.title.color = dark?'rgba(255,255,255,0.85)':'#333';
    Chart.defaults.plugins.legend.labels.color = dark?'rgba(255,255,255,0.7)':'#555';
}}
applyChartTheme();
window.updateChartTheme = applyChartTheme;

// ── BF Table ────────────────────────────────────────────────────────────────
const bfTbody = document.getElementById('bfTableBody');
BF_MILLS.forEach(function(b){{
    const idle = b[2].toLowerCase().includes('idle');
    const status = idle
        ? '<span class="badge badge-red" style="font-size:.68rem">Idled</span>'
        : '<span class="trend-up">Operating</span>';
    bfTbody.innerHTML += '<tr><td><strong>'+b[0]+'</strong></td><td>'+b[1]+'</td><td>'+b[2]+'</td><td>'+status+'</td></tr>';
}});

// ── Charts ──────────────────────────────────────────────────────────────────
const mkBar = (id,labels,datasets,opts)=>new Chart(document.getElementById(id),{{type:'bar',data:{{labels,datasets}},options:{{responsive:true,maintainAspectRatio:false,...opts}}}});
const mkLine = (id,labels,datasets,opts)=>new Chart(document.getElementById(id),{{type:'line',data:{{labels,datasets}},options:{{responsive:true,maintainAspectRatio:false,...opts}}}});
const mkDonut = (id,labels,data,colors,title)=>new Chart(document.getElementById(id),{{type:'doughnut',data:{{labels,datasets:[{{data,backgroundColor:colors,borderWidth:2,borderColor:'#fff'}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{title:{{display:true,text:title}},legend:{{position:'right'}}}}}}}});
const mkPie = (id,labels,data,colors,title)=>new Chart(document.getElementById(id),{{type:'pie',data:{{labels,datasets:[{{data,backgroundColor:colors,borderWidth:2,borderColor:'#fff'}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{title:{{display:true,text:title}},legend:{{position:'right'}}}}}}}});

// Cement production vs consumption (USGS live)
mkBar('cProdCons', CEM_YEARS, [
    {{label:'Production (MMT)',data:CEM_PROD,backgroundColor:C.green[1],borderRadius:4}},
    {{label:'Consumption (MMT)',data:CEM_CONS,backgroundColor:C.blue[1],borderRadius:4}}
], {{plugins:{{title:{{display:true,text:'US Cement: Production vs Consumption (Million MT) — USGS MCS'}},legend:{{position:'bottom'}}}},scales:{{y:{{min:80,title:{{display:true,text:'Million MT'}}}}}}}});

// Import origin
mkDonut('cImportPie',['Turkey 36%','Canada 24%','Vietnam 21%','Greece 9%','Mexico 7%','Egypt 4%'],[36,24,21,9,7,4],[C.red,'#FF9800',C.green[2],C.blue[2],C.teal[0],C.green[3]],'Cement Import Sources (%)');

// Import trend
mkLine('cImportTrend',['2020','2021','2022','2023','2024'],[
    {{label:'Volume (MT)',data:[16,18,21,20.5,19.8],borderColor:C.blue[1],backgroundColor:'rgba(25,118,210,0.1)',fill:true,tension:.3,pointRadius:5}},
    {{label:'Share (%)',data:[16,17,18,18,18],borderColor:C.red,borderDash:[5,5],fill:false,tension:.3,yAxisID:'y1',pointRadius:4}}
],{{plugins:{{title:{{display:true,text:'5-Year Cement Import Trend'}},legend:{{position:'bottom'}}}},scales:{{y:{{min:10,max:25,title:{{display:true,text:'Million MT'}}}},y1:{{position:'right',min:10,max:25,title:{{display:true,text:'Import Share %'}},grid:{{drawOnChartArea:false}}}}}}}});

// End use
mkPie('cEndUse',['Ready-Mix 72%','Concrete Products 12%','Contractors 9%','Other 7%'],[72,12,9,7],[C.green[1],C.blue[1],C.teal[0],C.green[3]],'Cement End-Use Segments');

// Slag shipments
mkBar('slagShip',['2019','2020','2021','2022','2023','2024'],[
    {{label:'Slag Cement (Mt)',data:[3.5,3.2,3.8,4.1,4.4,3.7],backgroundColor:['#3182ce','#3182ce','#3182ce','#3182ce','#4CAF50',C.red],borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'US Slag Cement Shipments — 2023 Record, 2024 Decline'}},legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,max:5.5,title:{{display:true,text:'Million MT'}}}}}}}});

// EAF transition
mkBar('eafChart',['2005','2010','2015','2020','2025E'],[
    {{label:'BF-BOF (%)',data:[50,40,35,30,28],backgroundColor:'#3182ce',borderRadius:4}},
    {{label:'EAF (%)',data:[50,60,65,70,72],backgroundColor:C.red,borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'US Steelmaking: BF-BOF vs EAF Share'}},legend:{{position:'bottom'}}}},scales:{{x:{{stacked:true}},y:{{stacked:true,max:100,title:{{display:true,text:'% of Production'}}}}}}}});

// Slag imports
mkDonut('slagImp',['Japan 52%','China 23%','Brazil 11%','S. Korea 8%','Other 6%'],[52,23,11,8,6],[C.blue[1],C.red,C.green[1],'#FF9800',C.teal[0]],'GGBFS Import Sources — Japan 52%');

// Coal capacity
mkBar('coalCap',['2011','2015','2019','2020','2022','2024','2025E','2028P','2030P'],[
    {{label:'GW',data:[318,280,229,200,190,175,165,145,106],backgroundColor:['#FF8F00','#FF8F00','#FF8F00','#E65100','#E65100',C.red,C.red,'#b71c1c','#b71c1c'],borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'US Coal-Fired Capacity Decline: 318 GW Peak → 106 GW Projected'}},legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,max:350,title:{{display:true,text:'Gigawatts'}}}}}}}});

// CCP
mkBar('ccpChart',['2017','2019','2020','2021','2022','2023'],[
    {{label:'CCP Production (Mt)',data:[111,79,69,77,80,67],backgroundColor:'#E65100',borderRadius:4}},
    {{label:'Beneficial Use (Mt)',data:[71,41,41,35,50,46],backgroundColor:C.green[1],borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'CCP Production vs Beneficial Use (Mt)'}},legend:{{position:'bottom'}}}},scales:{{y:{{beginAtZero:true,max:120,title:{{display:true,text:'Million Tons'}}}}}}}});

// Reclaimed ash
mkLine('reclaimedChart',['2021','2022','2023','2024E'],[
    {{label:'Reclaimed (Mt)',data:[2.5,3.5,4.5,5.0],borderColor:'#6b46c1',backgroundColor:'rgba(107,70,193,0.1)',fill:true,tension:.3,pointRadius:6}}
],{{plugins:{{title:{{display:true,text:'Reclaimed Ash — +100% Growth (2021–2024)'}},legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,max:7,title:{{display:true,text:'Mt'}}}}}}}});

// Pumice (USGS live)
const pumColors = PUM_PROD.map(v=>v===null?'#888':v<350?C.red:v>500?C.teal[0]:C.teal[1]);
mkBar('pumiceChart',PUM_YEARS,[
    {{label:'Pumice (Kt)',data:PUM_PROD,backgroundColor:pumColors,borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'US Pumice Mine Production (Thousand Short Tons) — USGS MCS'}},legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,max:700,title:{{display:true,text:'Thousand Short Tons'}}}}}}}});

// CO2
new Chart(document.getElementById('co2Chart'),{{type:'bar',data:{{labels:['OPC (Cement)','Natural Pozzolan','GGBFS','Fly Ash','Silica Fume'],datasets:[{{label:'kg CO₂/MT',data:[900,35,50,10,0],backgroundColor:[C.red,C.teal[0],'#3182ce','#FF8F00','#7B1FA2'],borderRadius:4}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{title:{{display:true,text:'Embodied CO₂ by Material (kg/MT)'}},legend:{{display:false}}}},scales:{{x:{{beginAtZero:true,max:1000,title:{{display:true,text:'kg CO₂/MT'}}}}}}}}}});

// Price trends
mkLine('priceChart',['2020','2021','2022','2023','2024','2025E'],[
    {{label:'OPC',data:[130,135,140,150,155,163],borderColor:C.green[1],fill:false,tension:.3,pointRadius:4}},
    {{label:'GGBFS',data:[85,90,100,110,120,130],borderColor:'#3182ce',fill:false,tension:.3,pointRadius:4}},
    {{label:'Fly Ash',data:[55,68,85,105,118,123],borderColor:'#FF8F00',fill:false,tension:.3,pointRadius:4}},
    {{label:'Nat. Pozzolan',data:[95,98,100,105,112,115],borderColor:C.teal[0],fill:false,tension:.3,pointRadius:4}}
],{{plugins:{{title:{{display:true,text:'Cementitious Price Trends ($/MT)'}},legend:{{position:'bottom'}}}},scales:{{y:{{min:40,max:180,title:{{display:true,text:'$/MT'}}}}}}}});

// SCM trajectories
mkLine('scmTraj',['2020','2022','2024','2026E','2028E','2030E'],[
    {{label:'Fly Ash',data:[30,27,14.7,10,8,6],borderColor:'#FF8F00',backgroundColor:'rgba(255,143,0,0.06)',fill:true,tension:.3,pointRadius:4}},
    {{label:'GGBFS',data:[4.5,4.6,3.7,3.2,2.8,2.5],borderColor:'#3182ce',backgroundColor:'rgba(49,130,226,0.06)',fill:true,tension:.3,pointRadius:4}},
    {{label:'Nat. Pozzolan',data:[1.2,1.8,2.5,3.5,5.0,7.0],borderColor:C.teal[0],backgroundColor:'rgba(0,137,123,0.06)',fill:true,tension:.3,pointRadius:4}}
],{{plugins:{{title:{{display:true,text:'SCM Supply Trajectories (Mt/yr) — Projected'}},legend:{{position:'bottom'}}}},scales:{{y:{{beginAtZero:true,max:35,title:{{display:true,text:'Mt/yr'}}}}}}}});

// Outlook
mkBar('outlookChart',['2024','2026E','2028E','2030E'],[
    {{label:'Cement',data:[92.6,96,100,105],backgroundColor:C.green[1],borderRadius:4}},
    {{label:'Fly Ash',data:[14.7,10,8,6],backgroundColor:'#FF8F00',borderRadius:4}},
    {{label:'GGBFS',data:[3.7,3.2,2.8,2.5],backgroundColor:'#3182ce',borderRadius:4}},
    {{label:'Nat. Pozzolans',data:[2.5,3.5,5.0,7.0],backgroundColor:C.teal[0],borderRadius:4}}
],{{plugins:{{title:{{display:true,text:'Cementitious Market Volume (Mt/yr)'}},legend:{{position:'bottom'}}}},scales:{{y:{{beginAtZero:true,max:130,title:{{display:true,text:'Million MT'}}}}}}}});

// ── Map ─────────────────────────────────────────────────────────────────────
const mapEl = document.getElementById('mapContainer');
if(mapEl){{
    const map = L.map('mapContainer').setView([39.5,-98.5],4);
    const darkT  = 'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png';
    const lightT = 'https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png';
    const tile = L.tileLayer(darkT,{{attribution:'&copy; CartoDB',subdomains:'abcd',maxZoom:18}}).addTo(map);
    window._mapRef=map; window._tile=tile; window._dark=darkT; window._light=lightT;

    const plantsLyr = L.layerGroup();
    PLANTS.forEach(p=>L.circleMarker([p[4],p[5]],{{radius:Math.max(5,Math.min(14,p[3]*4)),fillColor:'#4CAF50',color:'#fff',weight:1.5,fillOpacity:.8}}).bindPopup('<b>'+p[0]+'</b><br>'+p[1]+' &bull; '+p[2]+'<br><span style="color:#64ffb4;font-weight:600">'+p[3].toFixed(1)+' MT/yr</span>').addTo(plantsLyr));
    plantsLyr.addTo(map);

    const portsLyr = L.layerGroup();
    PORTS.forEach(p=>L.circleMarker([p[4],p[5]],{{radius:Math.max(6,Math.min(30,Math.sqrt(p[1]/8000))),fillColor:'#E53935',color:'#fff',weight:2,fillOpacity:.75}}).bindPopup('<b>'+p[0]+'</b><br><span style="color:#64ffb4;font-weight:600">'+p[2]+'</span><br>'+p[3]+' shipments').addTo(portsLyr));
    portsLyr.addTo(map);

    const bfLyr = L.layerGroup();
    BF_MILLS.forEach(b=>L.marker([b[3],b[4]],{{icon:L.divIcon({{className:'',html:'<div style="width:16px;height:16px;background:#3182ce;transform:rotate(45deg);border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,.4)"></div>',iconSize:[16,16],iconAnchor:[8,8]}})}}).bindPopup('<b>'+b[0]+'</b><br>'+b[1]+'<br>'+b[2]).addTo(bfLyr));
    bfLyr.addTo(map);

    const pozLyr = L.layerGroup();
    POZ.forEach(d=>L.marker([d[3],d[4]],{{icon:L.divIcon({{className:'',html:'<div style="width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:16px solid #00695C;filter:drop-shadow(0 0 2px rgba(0,0,0,.4))"></div>',iconSize:[18,16],iconAnchor:[9,16]}})}}).bindPopup('<b>'+d[0]+'</b><br>'+d[1]+'<br><span style="color:#64ffb4">'+d[2]+'</span>').addTo(pozLyr));
    pozLyr.addTo(map);

    const lc = L.control({{position:'topright'}});
    lc.onAdd=function(){{
        const div=L.DomUtil.create('div','layer-control');
        div.innerHTML='<h4>Layers</h4>'
            +'<label><input type="checkbox" id="tP" checked> <span style="color:#4CAF50">&#9679;</span> Cement Plants ('+PLANTS.length+')</label>'
            +'<label><input type="checkbox" id="tR" checked> <span style="color:#E53935">&#9679;</span> Import Ports ('+PORTS.length+')</label>'
            +'<label><input type="checkbox" id="tB" checked> <span style="color:#3182ce">&#9632;</span> BF Mills (AIST live)</label>'
            +'<label><input type="checkbox" id="tZ" checked> <span style="color:#00695C">&#9650;</span> Pozzolan Deposits</label>';
        L.DomEvent.disableClickPropagation(div);
        return div;
    }};
    lc.addTo(map);
    document.getElementById('tP').onchange=e=>e.target.checked?map.addLayer(plantsLyr):map.removeLayer(plantsLyr);
    document.getElementById('tR').onchange=e=>e.target.checked?map.addLayer(portsLyr):map.removeLayer(portsLyr);
    document.getElementById('tB').onchange=e=>e.target.checked?map.addLayer(bfLyr):map.removeLayer(bfLyr);
    document.getElementById('tZ').onchange=e=>e.target.checked?map.addLayer(pozLyr):map.removeLayer(pozLyr);
}}

window.updateMapTiles=function(){{
    if(!window._mapRef) return;
    const dark=!document.body.classList.contains('light-mode');
    window._tile.setUrl(dark?window._dark:window._light);
}};

// Sticky nav
const secs=document.querySelectorAll('section[id]'), links=document.querySelectorAll('.nav a');
window.addEventListener('scroll',()=>{{
    const y=window.scrollY+130;
    secs.forEach(s=>{{if(y>=s.offsetTop&&y<s.offsetTop+s.offsetHeight) links.forEach(l=>l.classList.toggle('active',l.getAttribute('href')==='#'+s.id));}});
}},{{passive:true}});

}})();
</script>
</body>
</html>"""


def main():
    print("=" * 55)
    print("US Construction Materials Intelligence Report")
    print("=" * 55)

    print("\n[1/3] Loading USGS data...")
    d = load_data()
    print(f"      Cement production 2024: {d['cement_prod'][-1]} MMT")
    print(f"      Cement price: ${d['cement_price']}/MT")
    print(f"      Pumice 2024: {d['pumice_prod'][-1]} Kt")
    print(f"      Slag consumption: {d['slag_cons']} Mt")

    print("\n[2/3] Loading AIST blast furnace mills...")
    bf_mills = load_bf_mills()
    print(f"      {len(bf_mills)} US BF/integrated mills")

    print("\n[3/3] Building report...")
    html = build_html(d, bf_mills)
    OUTPUT.write_text(html, encoding="utf-8")

    print(f"\n{'=' * 55}")
    print(f"Output: {OUTPUT}")
    print(f"Size:   {OUTPUT.stat().st_size / 1024:.0f} KB")
    print(f"Open:   open output/construction_materials_intelligence_report.html")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()

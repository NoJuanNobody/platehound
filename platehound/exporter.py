import csv
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

EXPORT_COLUMNS = [
    "id",
    "plate",
    "state",
    "make",
    "model",
    "year",
    "body_class",
    "engine_info",
    "drive_type",
    "fuel_type",
    "vin_masked",
    "lead_segment",
    "outreach_pitch",
    "sightings_count",
    "confidence",
    "source",
    "notes",
    "image_path",
    "created_at",
    "updated_at",
]

def export_csv(leads: List[Dict[str, Any]], output_path: str) -> str:
    """
    Exports a list of vehicle lead dictionaries to CSV.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            row = {col: lead.get(col, "") for col in EXPORT_COLUMNS}
            writer.writerow(row)
    return output_path

def export_json(leads: List[Dict[str, Any]], output_path: str) -> str:
    """
    Exports a list of vehicle lead dictionaries to formatted JSON.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, mode="w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)
    return output_path

def export_html_dashboard(
    leads: List[Dict[str, Any]],
    stats: Optional[Dict[str, Any]] = None,
    output_path: str = "outreach_leads.html"
) -> str:
    """
    Generates a sleek, self-contained dark-mode Homelab Outreach Leads Dashboard HTML page.
    Features:
      - Real-time client-side search across plate, specs, segment, notes, and pitch
      - Dynamic segment filter pills with count badges
      - Homelab KPI stat cards (Total Leads, Total Sightings, Avg Fleet Year, Segment Breakdown)
      - Florida License Plate visual render badges
      - One-click 'Copy Pitch' buttons with clipboard integration and visual feedback
      - Zero external CDN dependencies: fully operational in air-gapped homelab networks
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Compute stats if not provided
    if not stats:
        total_leads = len(leads)
        total_sightings = sum(int(l.get("sightings_count") or 1) for l in leads)
        years = [int(l["year"]) for l in leads if l.get("year")]
        avg_year = round(sum(years) / len(years), 1) if years else "N/A"
        by_segment: Dict[str, int] = {}
        for l in leads:
            seg = l.get("lead_segment") or "Unsegmented"
            by_segment[seg] = by_segment.get(seg, 0) + 1
        stats = {
            "total_leads": total_leads,
            "total_sightings": total_sightings,
            "average_year": avg_year,
            "by_lead_segment": by_segment,
        }

    total_leads = stats.get("total_leads", len(leads))
    total_sightings = stats.get("total_sightings", sum(int(l.get("sightings_count") or 1) for l in leads))
    avg_year = stats.get("average_year") or stats.get("avg_year") or "N/A"
    segments_dict = stats.get("by_lead_segment") or stats.get("lead_segment_breakdown") or {}

    # Extract distinct segments from actual leads for pills
    all_segments = set()
    for l in leads:
        seg = l.get("lead_segment") or "Unsegmented"
        all_segments.add(seg)
    sorted_segments = sorted(list(all_segments))

    # Pre-render rows/cards JSON safe for client-side search
    rendered_cards = []
    for l in leads:
        plate = str(l.get("plate", "")).upper()
        state = str(l.get("state", "FL")).upper()
        make = str(l.get("make") or "Unknown Make").upper()
        model = str(l.get("model") or "").upper()
        year = str(l.get("year") or "")
        body = str(l.get("body_class") or "Vehicle")
        engine = str(l.get("engine_info") or "Standard Powertrain")
        drive = str(l.get("drive_type") or "-")
        fuel = str(l.get("fuel_type") or "Gasoline")
        vin = str(l.get("vin_masked") or "1FTEW1...M921")
        segment = str(l.get("lead_segment") or "Unsegmented")
        pitch = str(l.get("outreach_pitch") or "Contact vehicle owner for commercial and trade-in upgrade options.")
        sightings = int(l.get("sightings_count") or 1)
        notes = str(l.get("notes") or "")
        confidence = float(l.get("confidence") or 1.0)
        updated = str(l.get("updated_at") or l.get("created_at") or datetime.now().strftime("%Y-%m-%d"))

        # Escape pitch for JS string in button onclick
        escaped_pitch = pitch.replace("\\", "\\\\").replace("'", "\\'").replace('"', '&quot;')

        card_html = f"""
        <div class="lead-card" data-segment="{segment.lower()}" data-search="{plate.lower()} {make.lower()} {model.lower()} {year.lower()} {body.lower()} {segment.lower()} {vin.lower()} {notes.lower()}">
            <div class="card-header">
                <div class="fl-plate-badge">
                    <div class="fl-plate-header">FLORIDA</div>
                    <div class="fl-plate-number">{plate}</div>
                    <div class="fl-plate-footer">SUNSHINE STATE</div>
                </div>
                <div class="header-badges">
                    <span class="badge badge-segment">{segment}</span>
                    <span class="badge badge-sightings">👁️ {sightings} sighting{'s' if sightings != 1 else ''}</span>
                    <span class="badge badge-confidence">{confidence*100:.0f}% ALPR Conf</span>
                </div>
            </div>
            
            <div class="vehicle-title">
                <span class="title-year">{year}</span>
                <span class="title-make-model">{make} {model}</span>
                <span class="title-body">({body})</span>
            </div>

            <div class="specs-grid">
                <div class="spec-item"><span class="spec-label">Engine:</span> <span class="spec-value">{engine}</span></div>
                <div class="spec-item"><span class="spec-label">Drive / Fuel:</span> <span class="spec-value">{drive} / {fuel}</span></div>
                <div class="spec-item"><span class="spec-label">Masked VIN:</span> <span class="spec-value code-font">{vin}</span></div>
                <div class="spec-item"><span class="spec-label">Last Seen:</span> <span class="spec-value">{updated}</span></div>
            </div>

            {f'<div class="notes-box"><strong>Observation:</strong> {notes}</div>' if notes else ''}

            <div class="pitch-container">
                <div class="pitch-header">
                    <span class="pitch-tag">⚡ TAILORED OUTREACH PITCH</span>
                    <button class="btn-copy" onclick="copyPitch(this, '{escaped_pitch}')">
                        <span class="btn-text">📋 Copy Pitch</span>
                    </button>
                </div>
                <div class="pitch-text">"{pitch}"</div>
            </div>
        </div>
        """
        rendered_cards.append(card_html)

    cards_joined = "\n".join(rendered_cards)

    # Segment filter buttons HTML
    pills_html = ['<button class="pill active" data-filter="all" onclick="filterSegment(\'all\', this)">All Leads <span class="pill-count">' + str(len(leads)) + '</span></button>']
    for seg in sorted_segments:
        count = sum(1 for l in leads if (l.get("lead_segment") or "Unsegmented") == seg)
        pills_html.append(f'<button class="pill" data-filter="{seg.lower()}" onclick="filterSegment(\'{seg.lower()}\', this)">{seg} <span class="pill-count">{count}</span></button>')
    pills_joined = "\n".join(pills_html)

    now_str = datetime.now().strftime("%b %d, %Y - %H:%M:%S")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PlateHound // Homelab Outreach Leads Dashboard</title>
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-surface: #111827;
            --bg-card: #141e33;
            --bg-card-hover: #192640;
            --border-color: #23314d;
            --border-subtle: #1c273e;
            --text-main: #f3f4f6;
            --text-muted: #94a3b8;
            --text-accent: #38bdf8;
            --color-emerald: #10b981;
            --color-amber: #f59e0b;
            --color-cyan: #06b6d4;
            --color-violet: #a855f7;
            --color-rose: #f43f5e;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-main);
            line-height: 1.5;
            padding: 24px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        /* Header */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .logo-area {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .logo-icon {{
            font-size: 32px;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }}
        .logo-text h1 {{
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .logo-text p {{
            font-size: 13px;
            color: var(--text-muted);
        }}
        .header-meta {{
            text-align: right;
        }}
        .homelab-badge {{
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 4px 10px;
            border-radius: 9999px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            margin-bottom: 6px;
        }}
        .timestamp {{
            font-size: 12px;
            color: var(--text-muted);
            font-family: monospace;
        }}

        /* KPI Stat Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--text-accent);
        }}
        .kpi-title {{
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .kpi-value {{
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            letter-spacing: -0.5px;
        }}
        .kpi-subtext {{
            font-size: 12px;
            color: var(--color-emerald);
            margin-top: 4px;
        }}

        /* Controls: Search and Filters */
        .controls-panel {{
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 24px;
        }}
        .search-box {{
            width: 100%;
            padding: 12px 18px;
            border-radius: 10px;
            background: #0d1320;
            border: 1px solid var(--border-color);
            color: #fff;
            font-size: 15px;
            outline: none;
            transition: border-color 0.2s;
            margin-bottom: 14px;
        }}
        .search-box:focus {{
            border-color: var(--text-accent);
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.15);
        }}
        .filter-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }}
        .pill {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .pill:hover {{
            color: #fff;
            border-color: var(--text-accent);
            background: var(--bg-card-hover);
        }}
        .pill.active {{
            background: #0284c7;
            color: #fff;
            border-color: #38bdf8;
            font-weight: 600;
        }}
        .pill-count {{
            font-size: 11px;
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 10px;
        }}
        .results-summary {{
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
        }}

        /* Leads Grid */
        .leads-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 20px;
        }}
        .lead-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            gap: 14px;
            transition: border-color 0.2s ease, transform 0.2s ease;
        }}
        .lead-card:hover {{
            border-color: #3b82f6;
            transform: translateY(-2px);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
        }}

        /* Authentic Florida Plate Render */
        .fl-plate-badge {{
            width: 140px;
            height: 68px;
            background: #ffffff;
            border: 3px solid #1e3a1e;
            border-radius: 6px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            padding: 3px 6px;
            box-shadow: 0 3px 8px rgba(0,0,0,0.5);
            flex-shrink: 0;
            position: relative;
        }}
        .fl-plate-header {{
            font-size: 10px;
            font-weight: 900;
            color: #15803d;
            letter-spacing: 1.5px;
            line-height: 1;
        }}
        .fl-plate-number {{
            font-family: "Courier New", Courier, monospace;
            font-size: 20px;
            font-weight: 900;
            color: #0f172a;
            letter-spacing: 1.5px;
            line-height: 1;
        }}
        .fl-plate-footer {{
            font-size: 8px;
            font-weight: 800;
            color: #c2410c;
            letter-spacing: 0.8px;
            line-height: 1;
        }}

        .header-badges {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 6px;
        }}
        .badge {{
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 6px;
            display: inline-block;
        }}
        .badge-segment {{
            background: rgba(168, 85, 247, 0.15);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.3);
        }}
        .badge-sightings {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}
        .badge-confidence {{
            background: rgba(6, 182, 212, 0.15);
            color: #22d3ee;
            border: 1px solid rgba(6, 182, 212, 0.3);
        }}

        .vehicle-title {{
            font-size: 17px;
            font-weight: 700;
            color: #fff;
            display: flex;
            gap: 6px;
            align-items: baseline;
            flex-wrap: wrap;
        }}
        .title-year {{
            color: var(--text-accent);
        }}
        .title-body {{
            font-size: 13px;
            font-weight: 400;
            color: var(--text-muted);
        }}

        .specs-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px 12px;
            background: var(--bg-card);
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid var(--border-subtle);
            font-size: 12px;
        }}
        .spec-item {{
            display: flex;
            flex-direction: column;
        }}
        .spec-label {{
            color: var(--text-muted);
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .spec-value {{
            color: #e2e8f0;
            font-weight: 500;
        }}
        .code-font {{
            font-family: monospace;
            color: #93c5fd;
        }}

        .notes-box {{
            font-size: 12px;
            background: rgba(0,0,0,0.25);
            border-left: 3px solid #3b82f6;
            padding: 6px 10px;
            border-radius: 4px;
            color: #cbd5e1;
        }}

        /* Pitch Box & Copy Button */
        .pitch-container {{
            background: linear-gradient(145deg, #132238, #0e1726);
            border: 1px solid #1e3a5f;
            border-radius: 10px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .pitch-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .pitch-tag {{
            font-size: 11px;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: 0.5px;
        }}
        .btn-copy {{
            background: #0284c7;
            color: #fff;
            border: none;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .btn-copy:hover {{
            background: #0369a1;
            box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
        }}
        .btn-copy.copied {{
            background: #059669;
        }}
        .pitch-text {{
            font-size: 13px;
            color: #e2e8f0;
            font-style: italic;
            line-height: 1.4;
        }}

        /* Empty state */
        .no-leads {{
            grid-column: 1 / -1;
            text-align: center;
            padding: 48px;
            color: var(--text-muted);
            background: var(--bg-surface);
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            display: none;
        }}

        @media (max-width: 600px) {{
            .leads-grid {{
                grid-template-columns: 1fr;
            }}
            .card-header {{
                flex-direction: column;
            }}
            .header-badges {{
                align-items: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-area">
                <div class="logo-icon">🐾</div>
                <div class="logo-text">
                    <h1>PlateHound Leads Command Center</h1>
                    <p>Florida ALPR Homelab Vehicle Intelligence & Outreach Pipeline</p>
                </div>
            </div>
            <div class="header-meta">
                <span class="homelab-badge">● AIR-GAPPED HOMELAB ACTIVE</span>
                <div class="timestamp">Generated: {now_str}</div>
            </div>
        </header>

        <!-- KPI Summary Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Vehicle Leads</div>
                <div class="kpi-value">{total_leads}</div>
                <div class="kpi-subtext">Unique Florida tags in CRM</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Total Sightings</div>
                <div class="kpi-value">{total_sightings}</div>
                <div class="kpi-subtext">Cumulative camera detections</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Avg Fleet Year</div>
                <div class="kpi-value">{avg_year}</div>
                <div class="kpi-subtext">Vehicle model year index</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Active Segments</div>
                <div class="kpi-value">{len(segments_dict)}</div>
                <div class="kpi-subtext">Lead categorization groups</div>
            </div>
        </div>

        <!-- Filter & Search Controls -->
        <div class="controls-panel">
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 Instant search by plate (e.g. 76BCDE), make, model, VIN, notes, or pitch..." oninput="handleSearch()">
            <div class="filter-pills" id="filterPills">
                {pills_joined}
            </div>
            <div class="results-summary">
                <span>Showing <strong id="visibleCount">{len(leads)}</strong> of <strong id="totalCount">{len(leads)}</strong> vehicle leads</span>
                <span id="activeFilterLabel">All Categories</span>
            </div>
        </div>

        <!-- Leads Card Grid -->
        <div class="leads-grid" id="leadsGrid">
            {cards_joined}
            <div class="no-leads" id="noLeadsState">
                <h3>No vehicle leads found matching your criteria.</h3>
                <p>Try clearing your search query or switching segment filters.</p>
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';

        function filterSegment(segment, element) {{
            currentFilter = segment.toLowerCase();
            document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            if (element) {{
                element.classList.add('active');
            }}
            document.getElementById('activeFilterLabel').innerText = 
                currentFilter === 'all' ? 'All Categories' : 'Segment: ' + segment;
            handleSearch();
        }}

        function handleSearch() {{
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            const cards = document.querySelectorAll('.lead-card');
            let visibleCount = 0;

            cards.forEach(card => {{
                const cardSegment = card.getAttribute('data-segment') || '';
                const cardSearch = card.getAttribute('data-search') || '';

                const matchesSegment = (currentFilter === 'all') || (cardSegment === currentFilter);
                const matchesQuery = !query || cardSearch.includes(query);

                if (matchesSegment && matchesQuery) {{
                    card.style.display = 'flex';
                    visibleCount++;
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            document.getElementById('visibleCount').innerText = visibleCount;
            const noLeads = document.getElementById('noLeadsState');
            if (noLeads) {{
                noLeads.style.display = visibleCount === 0 ? 'block' : 'none';
            }}
        }}

        function copyPitch(btn, text) {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(() => {{
                    showCopiedFeedback(btn);
                }}).catch(err => {{
                    fallbackCopy(btn, text);
                }});
            }} else {{
                fallbackCopy(btn, text);
            }}
        }}

        function fallbackCopy(btn, text) {{
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {{
                document.execCommand('copy');
                showCopiedFeedback(btn);
            }} catch (e) {{
                console.error('Could not copy pitch', e);
            }}
            document.body.removeChild(textarea);
        }}

        function showCopiedFeedback(btn) {{
            const btnText = btn.querySelector('.btn-text');
            const originalText = btnText ? btnText.innerText : btn.innerText;
            btn.classList.add('copied');
            if (btnText) btnText.innerText = '✅ Copied!';
            setTimeout(() => {{
                btn.classList.remove('copied');
                if (btnText) btnText.innerText = originalText;
            }}, 2000);
        }}
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path

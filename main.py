import json, os, re, glob, time, shutil, tempfile
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://yosintv.github.io/psg"

# Auto-detect system timezone offset
LOCAL_OFFSET = timezone(
    timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone)
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# Weekly menu center logic: today is the 4th item
MENU_START_DATE = TODAY_DATE - timedelta(days=3)
MENU_END_DATE = TODAY_DATE + timedelta(days=3)

# Top leagues used for ordering on daily pages
TOP_LEAGUE_IDS = [17, 35, 23, 7, 8, 34, 679]

# Google Ads placeholder block
ADS_CODE = '''
<div class="ad-container" style="margin: 20px 0; text-align: center;">
 
</div>
'''

# Footer HTML for home/index.html
FOOTER_HTML = '''
<footer style="margin-top: 40px; padding: 20px 0; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 14px;">
    <div style="max-width: 800px; margin: 0 auto; padding: 0 20px;">
        <p>⚽ Football TV Schedules • Updated automatically every hour</p>
        <p style="margin-top: 8px; font-size: 12px;">Live match listings may vary by region • Check local listings for confirmation</p>
    </div>
</footer>
'''

# Channel page header CSS + "Upcoming Live Matches on" styling
CHANNEL_HEADER_CSS = '''
<style>
.channel-header {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: white;
    padding: 24px 20px;
    border-radius: 12px 12px 0 0;
    margin: -20px -20px 20px -20px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}
.channel-header h1 {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 4px 0;
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.channel-header .subtitle {
    font-size: 16px;
    opacity: 0.9;
    margin: 0;
}
@media (max-width: 480px) {
    .channel-header h1 { font-size: 24px; }
    .channel-header .subtitle { font-size: 14px; }
}
</style>
'''

# Weekly menu CSS from build.py
MENU_CSS = '''
<style>
    .weekly-menu-container {
        display: flex;
        width: 100%;
        gap: 4px;
        padding: 10px 5px;
        box-sizing: border-box;
        justify-content: space-between;
    }
    .date-btn {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 8px 2px;
        text-decoration: none;
        border-radius: 6px;
        background: #fff;
        border: 1px solid #e2e8f0;
        min-width: 0; 
        transition: all 0.2s;
    }
    .date-btn div { font-size: 9px; text-transform: uppercase; color: #64748b; font-weight: bold; }
    .date-btn b { font-size: 10px; color: #1e293b; white-space: nowrap; }
    .date-btn.active { background: #2563eb; border-color: #2563eb; }
    .date-btn.active div, .date-btn.active b { color: #fff; }
    
    @media (max-width: 480px) {
        .date-btn b { font-size: 8px; }
        .date-btn div { font-size: 7px; }
        .weekly-menu-container { gap: 2px; padding: 5px 2px; }
    }
</style>
'''

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def atomic_write(relative_path, content):
    """Write file atomically directly to BASE_DIR."""
    full_path = os.path.join(BASE_DIR, relative_path)
    directory = os.path.dirname(full_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=directory or BASE_DIR, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        os.replace(tmp_path, full_path)
    except:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

# Clean existing folders (optional - remove if you want to keep old files)
for folder in ['home', 'match', 'channel']:
    folder_path = os.path.join(BASE_DIR, folder)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)

# --- 3. LOAD ORIGINAL TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    try:
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    except FileNotFoundError:
        print(f"❌ ERROR: {t_path} not found!")
        templates[name] = (
            "{{WEEKLY_MENU}}{{MATCH_LISTING}}"
            "{{BROADCAST_ROWS}}{{LEAGUE}}"
            "{{LOCAL_DATE}}{{LOCAL_TIME}}{{UNIX}}{{VENUE}}"
        )

# --- 4. LOAD DATA ---
all_matches = []
seen_match_ids = set()
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

for f in json_files:
    with open(f, 'r', encoding='utf-8') as j:
        try:
            data = json.load(j)
            if isinstance(data, dict):
                data = [data]
            for m in data:
                mid = m.get('match_id')
                if mid and mid not in seen_match_ids:
                    all_matches.append(m)
                    seen_match_ids.add(mid)
        except Exception:
            continue

print(f"⚽ Matches loaded: {len(all_matches)}")
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 5. SHARED UI: WEEKLY MENU ---
def build_weekly_menu():
    html = MENU_CSS + '<div class="weekly-menu-container">'
    for i in range(7):
        d = MENU_START_DATE + timedelta(days=i)
        d_str = d.strftime('%Y-%m-%d')
        active = "active" if d == TODAY_DATE else ""
        html += f'''
        <a href="{DOMAIN}/home/{d_str}.html" class="date-btn {active}">
            <div>{d.strftime("%a")}</div>
            <b>{d.strftime("%b %d")}</b>
        </a>'''
    html += '</div>'
    return html

WEEKLY_MENU_HTML = build_weekly_menu()

# --- 6. PAGE GENERATION ---

# 6a. Match Pages (8 placeholders) → match/{slug}/{YYYYMMDD}/index.html
for m in all_matches:
    try:
        m_dt = datetime.fromtimestamp(
            int(m['kickoff']), tz=timezone.utc
        ).astimezone(LOCAL_OFFSET)

        m_slug = slugify(m['fixture'])
        m_date_folder = m_dt.strftime('%Y%m%d')

        league = m.get('league', 'Other Football')
        venue_val = m.get('venue') or m.get('stadium') or "To Be Announced"

        # build broadcast rows (countries + channels)
        rows = ""
        country_counter = 0
        for c in m.get('tv_channels', []):
            country_counter += 1
            channel_links = [
                f'<a href="{DOMAIN}/channel/{slugify(ch)}/" '
                f'style="display: inline-block; background: #f1f5f9; '
                f'color: #2563eb; padding: 2px 8px; border-radius: 4px; '
                f'margin: 2px; text-decoration: none; font-weight: 600; '
                f'border: 1px solid #e2e8f0;">{ch}</a>'
                for ch in c['channels']
            ]
            pills = "".join(channel_links)

            rows += f'''
            <div style="display: flex; align-items: flex-start; padding: 12px; border-bottom: 1px solid #edf2f7; background: #fff;">
                <div style="flex: 0 0 100px; font-weight: 800; color: #475569; font-size: 13px; padding-top: 4px;">{c["country"]}</div>
                <div style="flex: 1; display: flex; flex-wrap: wrap; gap: 4px;">{pills}</div>
            </div>'''
            if country_counter % 10 == 0:
                rows += ADS_CODE

        # apply all 8 placeholders
        m_html = templates['match']
        m_html = m_html.replace("{{FIXTURE}}", m['fixture'])
        m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
        m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
        m_html = m_html.replace("{{LEAGUE}}", league)
        m_html = m_html.replace(
            "{{LOCAL_DATE}}",
            f'<span class="auto-date" data-unix="{m["kickoff"]}">'
            f'{m_dt.strftime("%d %b %Y")}</span>'
        )
        m_html = m_html.replace(
            "{{LOCAL_TIME}}",
            f'<span class="auto-time" data-unix="{m["kickoff"]}">'
            f'{m_dt.strftime("%H:%M")}</span>'
        )
        m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
        m_html = m_html.replace("{{VENUE}}", venue_val)

        atomic_write(f"match/{m_slug}/{m_date_folder}/index.html", m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_folder}/")

        # Channel aggregation
        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data:
                    channels_data[ch] = []
                channels_data[ch].append(m)
    except Exception:
        continue

# 6b. Daily Pages → home/{YYYY-MM-DD}.html + index.html (today) WITH FOOTER
ALL_DATES = sorted({
    datetime.fromtimestamp(
        int(m['kickoff']), tz=timezone.utc
    ).astimezone(LOCAL_OFFSET).date()
    for m in all_matches
})

for day in ALL_DATES:
    day_str = day.strftime('%Y-%m-%d')

    day_matches = [
        m for m in all_matches
        if datetime.fromtimestamp(
            int(m['kickoff']), tz=timezone.utc
        ).astimezone(LOCAL_OFFSET).date() == day
    ]

    day_matches.sort(
        key=lambda x: (
            x.get('league_id') not in TOP_LEAGUE_IDS,
            x.get('league', 'Other Football'),
            x['kickoff']
        )
    )

    listing_html = ""
    last_league = ""
    league_counter = 0

    for m in day_matches:
        league = m.get('league', 'Other Football')
        if league != last_league:
            if last_league != "":
                league_counter += 1
                if league_counter % 3 == 0:
                    listing_html += ADS_CODE
            listing_html += f'<div class="league-header">{league}</div>'
            last_league = league

        dt_m = datetime.fromtimestamp(
            int(m['kickoff']), tz=timezone.utc
        ).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"

        listing_html += f'''
        <a href="{m_url}" class="match-row flex items-center p-4 bg-white group border-b border-slate-100">
            <div class="time-box" style="min-width: 95px; text-align: center; border-right: 1px solid #edf2f7; margin-right: 10px;">
                <div class="text-[10px] uppercase text-slate-400 font-bold auto-date" data-unix="{m['kickoff']}">{dt_m.strftime('%d %b')}</div>
                <div class="font-bold text-blue-600 text-sm auto-time" data-unix="{m['kickoff']}">{dt_m.strftime('%H:%M')}</div>
            </div>
            <div class="flex-1">
                <span class="text-slate-800 font-semibold text-sm md:text-base">{m['fixture']}</span>
            </div>
        </a>'''

    if listing_html:
        listing_html += ADS_CODE

    h_output = templates['home']
    h_output = h_output.replace("{{MATCH_LISTING}}", listing_html + FOOTER_HTML)  # ADD FOOTER HERE
    h_output = h_output.replace("{{WEEKLY_MENU}}", WEEKLY_MENU_HTML)
    h_output = h_output.replace("{{DOMAIN}}", DOMAIN)
    h_output = h_output.replace(
        "{{SELECTED_DATE}}",
        day.strftime("%A, %b %d, %Y")
    )
    h_output = h_output.replace(
        "{{PAGE_TITLE}}",
        f"TV Channels For {day.strftime('%A, %b %d, %Y')}"
    )

    atomic_write(f"home/{day_str}.html", h_output)
    sitemap_urls.append(f"{DOMAIN}/home/{day_str}.html")
    if day == TODAY_DATE:
        atomic_write("index.html", h_output)

# 6c. Channel Pages → channel/{slug}/index.html WITH HEADER CSS
for ch_name, m_list in channels_data.items():
    c_slug = slugify(ch_name)
    c_listing = ""
    for m in sorted(m_list, key=lambda x: x['kickoff']):
        dt_m = datetime.fromtimestamp(
            int(m['kickoff']), tz=timezone.utc
        ).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"
        c_listing += (
            f'<li>{dt_m.strftime("%d %b %H:%M")} - '
            f'<a href="{m_url}">{m["fixture"]}</a></li>'
        )

    channel_header = f'''
    {CHANNEL_HEADER_CSS}
    <div class="channel-header">
        <h1>📺 {ch_name}</h1>
        <p class="subtitle">Upcoming Live Matches on {ch_name}</p>
    </div>
    '''

    c_html = templates['channel']
    c_html = c_html.replace("{{CHANNEL_NAME}}", ch_name)
    c_html = c_html.replace("{{MATCH_LISTING}}", channel_header + f"<ul>{c_listing}</ul>")
    c_html = c_html.replace("{{DOMAIN}}", DOMAIN)
    c_html = c_html.replace("{{WEEKLY_MENU}}", WEEKLY_MENU_HTML)

    atomic_write(f"channel/{c_slug}/index.html", c_html)
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

# 6d. Sitemap → sitemap.xml
sitemap = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
)
for url in sorted(set(sitemap_urls)):
    sitemap += (
        f'<url><loc>{url}</loc>'
        f'<lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
    )
sitemap += '</urlset>'
atomic_write("sitemap.xml", sitemap)

print("🏁 DONE. Files generated directly to home/, match/, channel/, and root with footer & channel styling.")

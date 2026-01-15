import json, os, re, glob, time, tempfile, shutil
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://yosintv.github.io/psg"
# Auto-detect system timezone offset
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))

# Directory management
DIST_DIR = "."  # We write to root for GitHub Pages
TEMP_DIR = "dist_temp"

# Clean and create temp directory for the build process
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)

NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# MENU LOGIC: Today is the 4th item (3 days back, 3 days forward)
MENU_START_DATE = TODAY_DATE - timedelta(days=3)
TOP_LEAGUE_IDS = [17, 35, 23, 7, 8, 34, 679]

# --- 2. STYLING & ADS ---
ADS_CODE = '<div class="ad-container" style="margin: 20px 0; text-align: center;"></div>'

MENU_CSS = '''
<style>
    .weekly-menu-container {
        display: flex; width: 100%; gap: 4px; padding: 10px 5px;
        box-sizing: border-box; justify-content: space-between;
    }
    .date-btn {
        flex: 1; display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 8px 2px; text-decoration: none;
        border-radius: 6px; background: #fff; border: 1px solid #e2e8f0;
        min-width: 0; transition: all 0.2s;
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

# --- 3. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def atomic_write(path, content):
    """Write file to the temporary directory structure."""
    full_path = os.path.join(TEMP_DIR, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)

# --- 4. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    try:
        with open(f'{name}_template.html', 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    except FileNotFoundError:
        print(f"CRITICAL: {name}_template.html missing!")
        templates[name] = "<html><body>{{WEEKLY_MENU}}{{MATCH_LISTING}}</body></html>"

# --- 5. LOAD DATA ---
all_matches = []
seen_match_ids = set()
json_files = glob.glob("date/*.json")
for f in json_files:
    with open(f, 'r', encoding='utf-8') as j:
        try:
            data = json.load(j)
            if isinstance(data, dict): data = [data]
            for m in data:
                mid = m.get('match_id')
                if mid and mid not in seen_match_ids:
                    all_matches.append(m)
                    seen_match_ids.add(mid)
        except: continue

print(f"⚽ Loaded {len(all_matches)} matches.")
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 6. GENERATE PAGES ---

# 6a. Match Pages
for m in all_matches:
    m_dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
    m_slug = slugify(m['fixture'])
    m_date_folder = m_dt.strftime('%Y%m%d')
    
    rows = ""
    for c in m.get('tv_channels', []):
        ch_links = [f'<a href="{DOMAIN}/channel/{slugify(ch)}/" class="ch-pill" style="display:inline-block; padding:2px 8px; background:#f1f5f9; border-radius:4px; margin:2px; text-decoration:none; color:#2563eb; border:1px solid #e2e8f0;">{ch}</a>' for ch in c['channels']]
        rows += f'<div style="padding:10px; border-bottom:1px solid #eee;"><b>{c["country"]}</b>: {"".join(ch_links)}</div>'

    m_html = templates['match'].replace("{{FIXTURE}}", m['fixture']).replace("{{DOMAIN}}", DOMAIN)
    m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
    m_html = m_html.replace("{{LOCAL_DATE}}", m_dt.strftime("%d %b %Y"))
    m_html = m_html.replace("{{LOCAL_TIME}}", m_dt.strftime("%H:%M"))
    m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
    
    atomic_write(f"match/{m_slug}/{m_date_folder}/index.html", m_html)
    sitemap_urls.append(f"{DOMAIN}/match/{m_slug}/{m_date_folder}/")

    # Group data for Channels
    for c in m.get('tv_channels', []):
        for ch in c['channels']:
            if ch not in channels_data: channels_data[ch] = []
            channels_data[ch].append(m)

# 6b. Daily Pages & Home Folder
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})

# Build Global Menu
global_menu = f'{MENU_CSS}<div class="weekly-menu-container">'
for j in range(7):
    m_day = MENU_START_DATE + timedelta(days=j)
    m_day_str = m_day.strftime('%Y-%m-%d')
    active_class = "active" if m_day == TODAY_DATE else ""
    # Links point to our /home/ date management folder
    m_url = f"{DOMAIN}/home/{m_day_str}.html"
    global_menu += f'<a href="{m_url}" class="date-btn {active_class}"><div>{m_day.strftime("%a")}</div><b>{m_day.strftime("%b %d")}</b></a>'
global_menu += '</div>'

for day in ALL_DATES:
    day_str = day.strftime('%Y-%m-%d')
    day_matches = [m for m in all_matches if datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
    # Sort by League Importance then Time
    day_matches.sort(key=lambda x: (x.get('league_id') not in TOP_LEAGUE_IDS, x.get('league', ''), x['kickoff']))
    
    listing_html, last_league = "", ""
    for m in day_matches:
        league = m.get('league', 'Other Football')
        if league != last_league:
            listing_html += f'<div class="league-header" style="background:#f8fafc; padding:8px; font-weight:bold; border-bottom:2px solid #2563eb;">{league}</div>'
            last_league = league
        
        dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"
        listing_html += f'''
        <a href="{m_url}" style="display:flex; align-items:center; padding:12px; border-bottom:1px solid #f1f5f9; text-decoration:none; color:inherit; background:#fff;">
            <div style="min-width:60px; font-weight:bold; color:#2563eb;">{dt_m.strftime('%H:%M')}</div>
            <div style="flex:1; font-weight:500;">{m['fixture']}</div>
        </a>'''

    h_output = templates['home'].replace("{{MATCH_LISTING}}", listing_html).replace("{{WEEKLY_MENU}}", global_menu)
    h_output = h_output.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Football on TV - {day_str}")
    
    # Save to home/ folder
    atomic_write(f"home/{day_str}.html", h_output)
    sitemap_urls.append(f"{DOMAIN}/home/{day_str}.html")
    # If today, save as index.html
    if day == TODAY_DATE:
        atomic_write("index.html", h_output)

# 6c. Channel Pages
for ch_name, matches in channels_data.items():
    c_slug = slugify(ch_name)
    c_list = ""
    matches.sort(key=lambda x: x['kickoff'])
    for m in matches:
        dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}/{dt_m.strftime('%Y%m%d')}/"
        c_list += f'<a href="{m_url}" style="display:block; padding:10px; border-bottom:1px solid #eee; text-decoration:none; color:#333;"><b>{dt_m.strftime("%d %b %H:%M")}</b> - {m["fixture"]}</a>'
    
    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", c_list).replace("{{WEEKLY_MENU}}", global_menu).replace("{{DOMAIN}}", DOMAIN)
    atomic_write(f"channel/{c_slug}/index.html", c_html)
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

# 6d. Sitemap
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(set(sitemap_urls)):
    sitemap += f'<url><loc>{url}</loc><lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
sitemap += '</urlset>'
atomic_write("sitemap.xml", sitemap)

# --- 7. DEPLOYMENT ---
print("📦 Build complete. Moving files to root...")
# In GitHub Actions, we move from TEMP_DIR to root
for root, dirs, files in os.walk(TEMP_DIR):
    for file in files:
        src = os.path.join(root, file)
        rel_path = os.path.relpath(src, TEMP_DIR)
        dest = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)

shutil.rmtree(TEMP_DIR)
print("🏁 DONE. All folders created and CSS applied.")

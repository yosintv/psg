import json, os, re, glob, time, shutil, tempfile 
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://tv.singhyogendra.com.np"

# FIX: Hardcode the Timezone to Nepal (UTC+5:45). 
# GitHub Actions runners always use UTC. Without this, your "Today" 
# will be 5 hours and 45 minutes behind, causing index.html to show yesterday's matches.
LOCAL_OFFSET = timezone(timedelta(hours=5, minutes=45))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Get current time in the target timezone
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# Weekly menu logic: fixed window (3 days back, today, 3 days forward)
# This ensures index.html is ALWAYS part of the generation cycle.
MENU_START_DATE = TODAY_DATE - timedelta(days=3)
TARGET_DATES = [MENU_START_DATE + timedelta(days=i) for i in range(7)]

# Top leagues used for ordering on daily pages
TOP_LEAGUE_IDS = [17, 35, 23, 7, 8, 34, 679]

# Google Ads placeholder block
ADS_CODE = '''
<div class="ad-container" style="margin: 20px 0; text-align: center;">
    
</div>
'''

# Home template CSS for weekly menu
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
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise e

def build_weekly_menu(current_page_date):
    """Generates menu HTML, highlighting the button for the date being viewed."""
    html = MENU_CSS + '<div class="weekly-menu-container">'
    for d in TARGET_DATES:
        d_str = d.strftime('%Y-%m-%d')
        # Link logic: Today points to root /, others to /home/
        link = f"{DOMAIN}/" if d == TODAY_DATE else f"{DOMAIN}/home/{d_str}.html"
        active_class = "active" if d == current_page_date else ""
        
        html += f'''
        <a href="{link}" class="date-btn {active_class}">
            <div>{d.strftime("%a")}</div>
            <b>{d.strftime("%b %d")}</b>
        </a>'''
    html += '</div>'
    return html

# Clean folders to avoid stale files
for folder in ['home', 'match', 'channel']:
    folder_path = os.path.join(BASE_DIR, folder)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    try:
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    except FileNotFoundError:
        print(f"❌ ERROR: {t_path} not found!")
        exit(1)

# --- 4. LOAD DATA ---
all_matches = []
seen_match_ids = set()
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

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
        except Exception:
            continue

print(f"⚽ Matches Loaded: {len(all_matches)}")
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# --- 5. PAGE GENERATION ---

# 5a. MATCH PAGES
for m in all_matches:
    try:
        m_dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_slug = slugify(m['fixture'])
        m_date_str = m_dt.strftime('%Y%m%d')
        match_filename = f"{m_slug}-{m_date_str}.html"

        rows = ""
        country_counter = 0
        for c in m.get('tv_channels', []):
            country_counter += 1
            ch_links = [f'<a href="{DOMAIN}/channel/{slugify(ch)}.html" style="display: inline-block; background: #f1f5f9; color: #2563eb; padding: 2px 8px; border-radius: 4px; margin: 2px; text-decoration: none; font-weight: 600; border: 1px solid #e2e8f0;">{ch}</a>' for ch in c['channels']]

            rows += f'''
            <div style="display: flex; align-items: flex-start; padding: 12px; border-bottom: 1px solid #edf2f7; background: #fff;">
            <div style="flex: 0 0 100px; font-weight: 800; color: #475569; font-size: 13px; padding-top: 4px;">{c["country"]}</div>
            <div style="flex: 1; display: flex; flex-wrap: wrap; gap: 4px;">{" ".join(ch_links)}</div>
            </div>'''
            
            if country_counter % 10 == 0: rows += ADS_CODE

        m_html = templates['match'].replace("{{FIXTURE}}", m['fixture']) \
                                   .replace("{{LEAGUE}}", m.get('league', 'Other Football')) \
                                   .replace("{{DOMAIN}}", DOMAIN) \
                                   .replace("{{BROADCAST_ROWS}}", rows) \
                                   .replace("{{LOCAL_DATE}}", f'<span class="auto-date" data-unix="{m["kickoff"]}">{m_dt.strftime("%d %b %Y")}</span>') \
                                   .replace("{{LOCAL_TIME}}", f'<span class="auto-time" data-unix="{m["kickoff"]}">{m_dt.strftime("%H:%M")}</span>') \
                                   .replace("{{DATE}}", m_dt.strftime("%Y-%m-%d")) \
                                   .replace("{{TIME}}", m_dt.strftime("%H:%M")) \
                                   .replace("{{UNIX}}", str(m['kickoff'])) \
                                   .replace("{{VENUE}}", m.get('venue') or m.get('stadium') or "To Be Announced")

        atomic_write(f"match/{match_filename}", m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{match_filename}")

        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = {}
                channels_data[ch][m['match_id']] = m
    except Exception:
        continue

# 5b. HOME PAGES & INDEX.HTML (FIXED RE-GENERATION)
# This loop now iterates through TARGET_DATES, ensuring files are ALWAYS created.
for day in TARGET_DATES:
    day_str = day.strftime('%Y-%m-%d')
    current_path = "/" if day == TODAY_DATE else f"/home/{day_str}.html"

    # Find matches for this specific day
    day_matches = [m for m in all_matches if 
        datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
    
    day_matches.sort(key=lambda x: (x.get('league_id') not in TOP_LEAGUE_IDS, x.get('league', 'Other Football'), x['kickoff']))

    listing_html = ""
    if not day_matches:
        listing_html = '<div style="text-align:center; padding:40px; color:#64748b;">No matches scheduled for this date. Check back later!</div>'
    else:
        last_league = ""
        league_counter = 0
        for m in day_matches:
            league = m.get('league', 'Other Football')
            if league != last_league:
                if last_league != "":
                    league_counter += 1
                    if league_counter % 3 == 0: listing_html += ADS_CODE
                listing_html += f'<div class="league-header">{league}</div>'
                last_league = league

            dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
            m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}-{dt_m.strftime('%Y%m%d')}.html"
            
            listing_html += f'''
            <a href="{m_url}" class="match-row flex items-center p-4 hover:bg-slate-50 transition-all">
                <div class="time-box">
                    <div class="text-[10px] uppercase text-slate-400 font-bold auto-date" data-unix="{m['kickoff']}">{dt_m.strftime('%d %b')}</div>
                    <div class="font-bold text-blue-600 text-sm auto-time" data-unix="{m['kickoff']}">{dt_m.strftime('%H:%M')}</div>
                </div>
                <div class="flex-1 ml-4">
                    <span class="text-slate-800 font-semibold">{m['fixture']}</span>
                </div>
            </a>'''
        listing_html += ADS_CODE

    h_output = templates['home'].replace("{{MATCH_LISTING}}", listing_html) \
                                .replace("{{WEEKLY_MENU}}", build_weekly_menu(day)) \
                                .replace("{{DOMAIN}}", DOMAIN) \
                                .replace("{{SELECTED_DATE}}", day.strftime("%A, %b %d, %Y")) \
                                .replace("{{PAGE_TITLE}}", f"TV Channels For {day.strftime('%A, %b %d, %Y')}") \
                                .replace("{{CURRENT_PATH}}", current_path)

    # WRITE TO HOME FOLDER
    atomic_write(f"home/{day_str}.html", h_output)
    sitemap_urls.append(f"{DOMAIN}/home/{day_str}.html")
    
    # WRITE TO ROOT (INDEX.HTML)
    if day == TODAY_DATE:
        atomic_write("index.html", h_output)
        print(f"✅ index.html and home/{day_str}.html successfully updated for Today.")

# 5c. CHANNEL PAGES
for ch_name, match_dict in channels_data.items():
    c_slug = slugify(ch_name)
    unique_matches = sorted(list(match_dict.values()), key=lambda x: x['kickoff'])
    
    c_listing = ""
    for m in unique_matches:
        dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        m_url = f"{DOMAIN}/match/{slugify(m['fixture'])}-{dt_m.strftime('%Y%m%d')}.html"
        c_listing += f'''
        <div class="match-row">
            <div class="time-box">
                <div class="text-[10px] uppercase text-slate-400 font-bold auto-date" data-unix="{m['kickoff']}">{dt_m.strftime('%d %b')}</div>
                <div class="font-bold text-blue-600 text-sm auto-time" data-unix="{m['kickoff']}">{dt_m.strftime('%H:%M')}</div>
            </div>
            <div class="flex-1 ml-4">
                <a href="{m_url}" class="text-slate-800 font-semibold">{m['fixture']}</a>
            </div>
        </div>'''

    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name) \
                                 .replace("{{MATCH_LISTING}}", c_listing) \
                                 .replace("{{DOMAIN}}", DOMAIN)

    atomic_write(f"channel/{c_slug}.html", c_html)
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}.html")

# 5d. SITEMAP
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(list(set(sitemap_urls))):
    sitemap += f'<url><loc>{url}</loc><lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod></url>'
sitemap += '</urlset>'
atomic_write("sitemap.xml", sitemap)

print("🏁 Deployment Ready: index.html and home/ files are generated.")

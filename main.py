import json, os, re, glob, time, shutil, tempfile
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
DOMAIN = "https://tv.cricfoot.net"
LOCAL_OFFSET = timezone(timedelta(hours=5, minutes=45)) # Nepal Time
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define supported languages and UI translations
LOCALES = {
    "en": {
        "path_prefix": "",  # Root for English
        "lang_name": "English",
        "no_matches": "No matches scheduled for this date.",
        "league_other": "Other Football",
        "page_title_prefix": "TV Channels For",
        "venue_tba": "To Be Announced"
    },
    "pt": {
        "path_prefix": "pt/", # Portuguese subfolders
        "lang_name": "Português",
        "no_matches": "Nenhum jogo agendado para esta data.",
        "league_other": "Outro Futebol",
        "page_title_prefix": "Canais de TV para",
        "venue_tba": "A ser anunciado"
    }
}

NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()
MENU_START_DATE = TODAY_DATE - timedelta(days=3)
DISPLAY_MENU_DATES = [MENU_START_DATE + timedelta(days=i) for i in range(7)]
TOP_LEAGUE_IDS = [17, 35, 23, 7, 8, 34, 679]

ADS_CODE = '''<div class="ad-container" style="margin: 20px 0; text-align: center;">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5525538810839147"
     crossorigin="anonymous"></script>
<!-- Ressponsive -->
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-5525538810839147"
     data-ad-slot="4345862479"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({});
</script>
</div>'''

MENU_CSS = '''
<style>
    .weekly-menu-container { display: flex; width: 100%; gap: 4px; padding: 10px 5px; box-sizing: border-box; justify-content: space-between; }
    .date-btn { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 8px 2px; text-decoration: none; border-radius: 6px; background: #fff; border: 1px solid #e2e8f0; min-width: 0; transition: all 0.2s; }
    .date-btn div { font-size: 9px; text-transform: uppercase; color: #64748b; font-weight: bold; }
    .date-btn b { font-size: 10px; color: #1e293b; white-space: nowrap; }
    .date-btn.active { background: #2563eb; border-color: #2563eb; }
    .date-btn.active div, .date-btn.active b { color: #fff; }
    @media (max-width: 480px) { .date-btn b { font-size: 8px; } .date-btn div { font-size: 7px; } .weekly-menu-container { gap: 2px; padding: 5px 2px; } }
</style>
'''

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def atomic_write(relative_path, content):
    """Write file atomically including the nested language folders."""
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

def build_weekly_menu(current_page_date, lang_prefix):
    """Generates the visual 7-day menu HTML with language-specific links."""
    html = MENU_CSS + '<div class="weekly-menu-container">'
    for d in DISPLAY_MENU_DATES:
        d_str = d.strftime('%Y-%m-%d')
        # If today, link to / or /pt/, else link to /home/date.html or /pt/home/date.html
        if d == TODAY_DATE:
            link = f"{DOMAIN}/{lang_prefix}"
        else:
            link = f"{DOMAIN}/{lang_prefix}home/{d_str}.html"
            
        active_class = "active" if d == current_page_date else ""
        html += f'''
        <a href="{link}" class="date-btn {active_class}">
            <div>{d.strftime("%a")}</div>
            <b>{d.strftime("%b %d")}</b>
        </a>'''
    html += '</div>'
    return html

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
unique_dates = {TODAY_DATE} 
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
                    m_date = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date()
                    unique_dates.add(m_date)
        except Exception:
            continue

ALL_GENERATION_DATES = sorted(list(unique_dates))
now_unix = int(time.time())

# We will store sitemap URLs here: { "relative_path": { "en": "full_url", "pt": "full_url" } }
sitemap_registry = {}

# --- 5. MULTI-LANGUAGE GENERATION LOOP ---
for lang_code, cfg in LOCALES.items():
    prefix = cfg['path_prefix']
    channels_data = {}

    # 5a. MATCH PAGES
    for m in all_matches:
        try:
            m_dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
            m_slug = slugify(m['fixture'])
            m_date_str = m_dt.strftime('%Y%m%d')
            match_rel_path = f"match/{m_slug}-{m_date_str}.html"
            
            # Register for sitemap (key is the same across languages)
            if match_rel_path not in sitemap_registry: sitemap_registry[match_rel_path] = {}
            sitemap_registry[match_rel_path][lang_code] = f"{DOMAIN}/{prefix}{match_rel_path}"

            rows = ""
            for i, c in enumerate(m.get('tv_channels', [])):
                ch_links = [f'<a href="{DOMAIN}/{prefix}channel/{slugify(ch)}.html" class="channel-link" style="display: inline-block; background: #f1f5f9; color: #2563eb; padding: 2px 8px; border-radius: 4px; margin: 2px; text-decoration: none; font-weight: 600; border: 1px solid #e2e8f0;">{ch}</a>' for ch in c['channels']]
                rows += f'''<div style="display: flex; align-items: flex-start; padding: 12px; border-bottom: 1px solid #edf2f7; background: #fff;">
                            <div style="flex: 0 0 100px; font-weight: 800; color: #475569; font-size: 13px; padding-top: 4px;">{c["country"]}</div>
                            <div style="flex: 1; display: flex; flex-wrap: wrap; gap: 4px;">{" ".join(ch_links)}</div></div>'''
                if (i + 1) % 10 == 0: rows += ADS_CODE

            m_html = templates['match'].replace("{{FIXTURE}}", m['fixture']) \
                                       .replace("{{LEAGUE}}", m.get('league', cfg['league_other'])) \
                                       .replace("{{DOMAIN}}", DOMAIN) \
                                       .replace("{{BROADCAST_ROWS}}", rows) \
                                       .replace("{{LOCAL_DATE}}", m_dt.strftime("%d %b %Y")) \
                                       .replace("{{LOCAL_TIME}}", m_dt.strftime("%H:%M")) \
                                       .replace("{{UNIX}}", str(m['kickoff'])) \
                                       .replace("{{VENUE}}", m.get('venue') or m.get('stadium') or cfg['venue_tba'])

            atomic_write(f"{prefix}{match_rel_path}", m_html)

            for c in m.get('tv_channels', []):
                for ch in c['channels']:
                    if ch not in channels_data: channels_data[ch] = {}
                    channels_data[ch][m['match_id']] = m
        except Exception: continue

    # 5b. HOME PAGES
    for day in ALL_GENERATION_DATES:
        day_str = day.strftime('%Y-%m-%d')
        home_rel_path = f"home/{day_str}.html"
        
        if home_rel_path not in sitemap_registry: sitemap_registry[home_rel_path] = {}
        sitemap_registry[home_rel_path][lang_code] = f"{DOMAIN}/{prefix}{home_rel_path}"
        if day == TODAY_DATE:
            index_key = "index.html"
            if index_key not in sitemap_registry: sitemap_registry[index_key] = {}
            sitemap_registry[index_key][lang_code] = f"{DOMAIN}/{prefix}"

        day_matches = [m for m in all_matches if datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day]
        day_matches.sort(key=lambda x: (x.get('league_id') not in TOP_LEAGUE_IDS, x.get('league', cfg['league_other']), x['kickoff']))

        listing_html = ""
        if not day_matches:
            listing_html = f'<div style="text-align:center; padding:40px; color:#64748b;">{cfg["no_matches"]}</div>'
        else:
            last_league = ""
            league_cnt = 0
            for m in day_matches:
                league = m.get('league', cfg['league_other'])
                if league != last_league:
                    if last_league != "":
                        league_cnt += 1
                        if league_cnt % 3 == 0: listing_html += ADS_CODE
                    listing_html += f'<div class="league-header">{league}</div>'
                    last_league = league
                dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
                m_url = f"{DOMAIN}/{prefix}match/{slugify(m['fixture'])}-{dt_m.strftime('%Y%m%d')}.html"
                listing_html += f'''<a href="{m_url}" class="match-row flex items-center p-4 hover:bg-slate-50 transition-all">
                                    <div class="time-box">
                                        <div class="text-[10px] uppercase text-slate-400 font-bold">{dt_m.strftime('%d %b')}</div>
                                        <div class="font-bold text-blue-600 text-sm">{dt_m.strftime('%H:%M')}</div>
                                    </div>
                                    <div class="flex-1 ml-4"><span class="text-slate-800 font-semibold">{m['fixture']}</span></div></a>'''
            listing_html += ADS_CODE

        h_output = templates['home'].replace("{{MATCH_LISTING}}", listing_html) \
                                    .replace("{{WEEKLY_MENU}}", build_weekly_menu(day, prefix)) \
                                    .replace("{{DOMAIN}}", DOMAIN) \
                                    .replace("{{SELECTED_DATE}}", day.strftime("%A, %b %d, %Y")) \
                                    .replace("{{PAGE_TITLE}}", f"{cfg['page_title_prefix']} {day.strftime('%A, %b %d, %Y')}")
        
        atomic_write(f"{prefix}{home_rel_path}", h_output)
        if day == TODAY_DATE: atomic_write(f"{prefix}index.html", h_output)

    # 5c. CHANNEL PAGES
    for ch_name, match_dict in channels_data.items():
        c_slug = slugify(ch_name)
        channel_rel_path = f"channel/{c_slug}.html"
        
        if channel_rel_path not in sitemap_registry: sitemap_registry[channel_rel_path] = {}
        sitemap_registry[channel_rel_path][lang_code] = f"{DOMAIN}/{prefix}{channel_rel_path}"

        unique_matches = sorted(list(match_dict.values()), key=lambda x: x['kickoff'])
        c_listing = ""
        for m in unique_matches:
            if (int(m['kickoff']) + 7200) < now_unix: continue
            dt_m = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
            m_url = f"{DOMAIN}/{prefix}match/{slugify(m['fixture'])}-{dt_m.strftime('%Y%m%d')}.html"
            c_listing += f'''<div class="match-row"><div class="time-box">
                            <div class="text-[10px] uppercase text-slate-400 font-bold">{dt_m.strftime('%d %b')}</div>
                            <div class="font-bold text-blue-600 text-sm">{dt_m.strftime('%H:%M')}</div></div>
                            <div class="flex-1 ml-4"><a href="{m_url}" class="text-slate-800 font-semibold block">{m['fixture']}</a>
                            <div class="league-name text-slate-500 text-xs mt-1">{m.get('league', cfg['league_other'])}</div></div></div>'''
        
        if not c_listing: c_listing = f'<div style="text-align:center; padding:40px; color:#64748b;">{cfg["no_matches"]}</div>'
        
        c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", c_listing).replace("{{DOMAIN}}", DOMAIN)
        atomic_write(f"{prefix}{channel_rel_path}", c_html)

# --- 6. MULTI-LANGUAGE SITEMAP ---
sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
for rel_path, lang_urls in sitemap_registry.items():
    for l_code, loc_url in lang_urls.items():
        sitemap += f'  <url>\n    <loc>{loc_url}</loc>\n'
        for alt_code, alt_url in lang_urls.items():
            sitemap += f'    <xhtml:link rel="alternate" hreflang="{alt_code}" href="{alt_url}"/>\n'
        sitemap += f'    <lastmod>{NOW.strftime("%Y-%m-%d")}</lastmod>\n  </url>\n'
sitemap += '</urlset>'
atomic_write("sitemap.xml", sitemap)

print(f"🏁 Multi-language Deployment Ready for {list(LOCALES.keys())}")

import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
# Base domain as requested
DOMAIN = "https://yosintv.github.io/psg"
# Using UTC (0 offset) to ensure consistent date handling on GitHub servers
LOCAL_OFFSET = timezone(timedelta(hours=0)) 
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

# Absolute path to the repository root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 2. HELPERS ---
def slugify(t):
    """Converts names into URL-friendly strings."""
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def force_write(relative_path, content):
    """Creates any missing folders and writes the file."""
    full_path = os.path.join(BASE_DIR, relative_path)
    # Ensure the directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Generated: {relative_path}")

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    if os.path.exists(t_path):
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    else:
        # Fallback if your template file is missing or renamed
        templates[name] = "<html><body><h1>{{PAGE_TITLE}}</h1>{{WEEKLY_MENU}}{{MATCH_LISTING}}{{BROADCAST_ROWS}}{{FAQ_COUNTRY_ROWS}}</body></html>"

# --- 4. LOAD JSON DATA ---
all_matches = []
seen_ids = set()
# Grabbing all JSON files from the 'date' folder
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json"))

for f in json_files:
    try:
        with open(f, 'r', encoding='utf-8') as j:
            data = json.load(j)
            if isinstance(data, dict): data = [data]
            for m in data:
                # Ensure match has required data and avoid duplicates
                if m.get('match_id') and m.get('kickoff') and m['match_id'] not in seen_ids:
                    all_matches.append(m)
                    seen_ids.add(m['match_id'])
    except Exception as e:
        print(f"⚠️ Error reading {f}: {e}")

print(f"⚽ Found {len(all_matches)} total matches.")

if not all_matches:
    print("❌ CRITICAL ERROR: No match data found. Exiting.")
    exit(1)

# --- 5. PAGE GENERATION ---
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# 5a. GENERATE MATCH PAGES (match/slug/date/index.html)
for m in all_matches:
    try:
        dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc)
        slug = slugify(m['fixture'])
        date_folder = dt.strftime('%Y%m%d')
        
        # Build Channel Broadcast Rows
        rows = ""
        faq_html = ""
        for c in m.get('tv_channels', []):
            ch_list = c['channels']
            pills = " ".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/" class="ch-pill">{ch}</a>' for ch in ch_list])
            rows += f'<div class="country-row"><b>{c["country"]}</b>: {pills}</div>'
            faq_html += f'<div class="faq-item"><b>Where to watch {m["fixture"]} in {c["country"]}?</b><p>You can watch it on {", ".join(ch_list)}.</p></div>'

        # Inject data into match template
        m_html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
        m_html = m_html.replace("{{BROADCAST_ROWS}}", rows)
        m_html = m_html.replace("{{FAQ_COUNTRY_ROWS}}", faq_html)
        m_html = m_html.replace("{{LOCAL_TIME}}", dt.strftime("%H:%M"))
        m_html = m_html.replace("{{LOCAL_DATE}}", dt.strftime("%d %b %Y"))
        m_html = m_html.replace("{{UNIX}}", str(m['kickoff']))
        m_html = m_html.replace("{{DOMAIN}}", DOMAIN)
        
        # Save nested path
        force_write(f"match/{slug}/{date_folder}/index.html", m_html)
        sitemap_urls.append(f"{DOMAIN}/match/{slug}/{date_folder}/")

        # Track channels for the channel pages
        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = []
                channels_data[ch].append(m)
    except Exception as e:
        continue

# 5b. GENERATE DAILY PAGES (home/YYYY-MM-DD.html)
# Collect all unique dates from the data
all_days = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).date() for m in all_matches})

# Prepare the Weekly Menu once
menu_list = []
for d in all_days:
    # Pointing to the home/ folder links you requested
    link = f"{DOMAIN}/home/{d.strftime('%Y-%m-%d')}.html"
    menu_list.append(f'<a href="{link}" class="menu-item">{d.strftime("%b %d")}</a>')
menu_html = " | ".join(menu_list)

for day in all_days:
    day_str = day.strftime('%Y-%m-%d')
    # Filter matches for just this specific day
    day_matches = sorted([x for x in all_matches if datetime.fromtimestamp(int(x['kickoff']), tz=timezone.utc).date() == day], key=lambda x: x['kickoff'])
    
    match_list_html = ""
    for dm in day_matches:
        d_dt = datetime.fromtimestamp(int(dm['kickoff']), tz=timezone.utc)
        m_url = f"{DOMAIN}/match/{slugify(dm['fixture'])}/{d_dt.strftime('%Y%m%d')}/"
        match_list_html += f'<li><span class="time">{d_dt.strftime("%H:%M")}</span> <a href="{m_url}">{dm["fixture"]}</a></li>'
    
    # Inject data into home template
    h_html = templates['home'].replace("{{MATCH_LISTING}}", f"<ul>{match_list_html}</ul>").replace("{{WEEKLY_MENU}}", menu_html)
    h_html = h_html.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Schedule for {day_str}")
    
    # Write to home/ folder as requested
    force_write(f"home/{day_str}.html", h_html)
    sitemap_urls.append(f"{DOMAIN}/home/{day_str}.html")

    # Mirror today's file to index.html at the root for the landing page
    if day == TODAY_DATE:
        force_write("index.html", h_html)

# 5c. GENERATE CHANNEL PAGES (channel/slug/index.html)
for ch_name, m_list in channels_data.items():
    c_slug = slugify(ch_name)
    # Sort matches for this channel by time
    c_list_html = ""
    for mx in sorted(m_list, key=lambda x: x['kickoff']):
        mx_dt = datetime.fromtimestamp(int(mx['kickoff']), tz=timezone.utc)
        c_list_html += f'<li><a href="{DOMAIN}/match/{slugify(mx["fixture"])}/{mx_dt.strftime("%Y%m%d")}/">{mx["fixture"]}</a> ({mx_dt.strftime("%d %b")})</li>'
    
    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", f"<ul>{c_list_html}</ul>").replace("{{DOMAIN}}", DOMAIN)
    force_write(f"channel/{c_slug}/index.html", c_html)
    sitemap_urls.append(f"{DOMAIN}/channel/{c_slug}/")

# 5d. GENERATE SITEMAP.XML
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
for url in sorted(set(sitemap_urls)):
    sitemap += f'<url><loc>{url}</loc></url>'
sitemap += '</urlset>'
force_write("sitemap.xml", sitemap)

print("🏁 ALL PAGES GENERATED SUCCESSFULLY IN ROOT, MATCH/, CHANNEL/, AND HOME/ FOLDERS.")

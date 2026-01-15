import json, os, re, glob, time
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION ---
# Updated to your actual GitHub Pages URL
DOMAIN = "https://yosintv.github.io" 
LOCAL_OFFSET = timezone(timedelta(seconds=-time.timezone if time.daylight == 0 else -time.altzone))
NOW = datetime.now(LOCAL_OFFSET)
TODAY_DATE = NOW.date()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"🚀 Environment Check. Base Directory: {BASE_DIR}")

# --- DEBUG: LIST ALL FILES ---
print("📂 Current Files in Repo:")
for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if not file.startswith('.'): # Hide hidden git files
            print(f"  - {os.path.relpath(os.path.join(root, file), BASE_DIR)}")

# --- 2. HELPERS ---
def slugify(t):
    return re.sub(r'[^a-z0-9]+', '-', str(t).lower()).strip('-')

def safe_write(relative_path, content):
    full_path = os.path.join(BASE_DIR, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created: {relative_path}")

# --- 3. LOAD TEMPLATES ---
templates = {}
for name in ['home', 'match', 'channel']:
    t_path = os.path.join(BASE_DIR, f'{name}_template.html')
    if os.path.exists(t_path):
        with open(t_path, 'r', encoding='utf-8') as f:
            templates[name] = f.read()
    else:
        print(f"⚠️ Warning: {name}_template.html missing. Using empty shell.")
        templates[name] = "<html><body>{{WEEKLY_MENU}}{{MATCH_LISTING}}{{BROADCAST_ROWS}}{{FAQ_COUNTRY_ROWS}}</body></html>"

# --- 4. LOAD DATA (Aggressive Search) ---
all_matches = []
seen_ids = set()
# Search in 'date' folder and root
json_files = glob.glob(os.path.join(BASE_DIR, "date", "*.json")) + glob.glob(os.path.join(BASE_DIR, "*.json"))

print(f"🔍 Found {len(json_files)} JSON files to process.")

for f in json_files:
    if "package.json" in f: continue # Skip system files
    try:
        with open(f, 'r', encoding='utf-8') as j:
            data = json.load(j)
            if isinstance(data, dict): data = [data]
            for m in data:
                # Ensure it's a match object with a kickoff time
                if m.get('match_id') and m.get('kickoff') and m['match_id'] not in seen_ids:
                    all_matches.append(m)
                    seen_ids.add(m['match_id'])
    except Exception as e:
        print(f"❌ Skip {f}: {e}")

print(f"⚽ TOTAL MATCHES LOADED: {len(all_matches)}")

if not all_matches:
    print("⛔ CRITICAL: No matches found in JSON. Check scraper output.")
    exit(1)

# --- 5. GENERATE PAGES ---
channels_data = {}
sitemap_urls = [DOMAIN + "/"]

# 5a. Match Pages
for m in all_matches:
    try:
        dt = datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET)
        slug = slugify(m['fixture'])
        date_dir = dt.strftime('%Y%m%d')
        
        rows = ""
        faq = ""
        for c in m.get('tv_channels', []):
            ch_list = c['channels']
            pills = " ".join([f'<a href="{DOMAIN}/channel/{slugify(ch)}/">{ch}</a>' for ch in ch_list])
            rows += f"<div>{c['country']}: {pills}</div>"
            faq += f"<div><b>How to watch in {c['country']}?</b><p>On {', '.join(ch_list)}</p></div>"

        html = templates['match'].replace("{{FIXTURE}}", m['fixture'])
        html = html.replace("{{BROADCAST_ROWS}}", rows).replace("{{FAQ_COUNTRY_ROWS}}", faq)
        html = html.replace("{{LOCAL_TIME}}", dt.strftime("%H:%M")).replace("{{UNIX}}", str(m['kickoff']))
        html = html.replace("{{LOCAL_DATE}}", dt.strftime("%d %b %Y")).replace("{{DOMAIN}}", DOMAIN)
        
        safe_write(f"match/{slug}/{date_dir}/index.html", html)
        sitemap_urls.append(f"{DOMAIN}/match/{slug}/{date_dir}/")

        for c in m.get('tv_channels', []):
            for ch in c['channels']:
                if ch not in channels_data: channels_data[ch] = []
                channels_data[ch].append(m)
    except: continue

# 5b. Daily & Home Pages
ALL_DATES = sorted({datetime.fromtimestamp(int(m['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() for m in all_matches})
for day in ALL_DATES:
    f_name = "index.html" if day == TODAY_DATE else f"{day.strftime('%Y-%m-%d')}.html"
    
    day_m = sorted([x for x in all_matches if datetime.fromtimestamp(int(x['kickoff']), tz=timezone.utc).astimezone(LOCAL_OFFSET).date() == day], key=lambda x: x['kickoff'])
    list_html = "".join([f'<li>{datetime.fromtimestamp(int(dm["kickoff"]), tz=timezone.utc).astimezone(LOCAL_OFFSET).strftime("%H:%M")} <a href="{DOMAIN}/match/{slugify(dm["fixture"])}/{datetime.fromtimestamp(int(dm["kickoff"]), tz=timezone.utc).astimezone(LOCAL_OFFSET).strftime("%Y%m%d")}/">{dm["fixture"]}</a></li>' for dm in day_m])
    
    menu = " ".join([f'<a href="{DOMAIN}/{"index.html" if d==TODAY_DATE else d.strftime("%Y-%m-%d")+".html"}">{d.strftime("%b %d")}</a>' for d in ALL_DATES[:7]])

    h_html = templates['home'].replace("{{MATCH_LISTING}}", f"<ul>{list_html}</ul>").replace("{{WEEKLY_MENU}}", menu)
    h_html = h_html.replace("{{DOMAIN}}", DOMAIN).replace("{{PAGE_TITLE}}", f"Football TV Guide {day}")
    safe_write(f_name, h_html)

# 5c. Channel Pages
for ch_name, m_list in channels_data.items():
    c_slug = slugify(ch_name)
    c_list = "".join([f'<li><a href="{DOMAIN}/match/{slugify(mx["fixture"])}/{datetime.fromtimestamp(int(mx["kickoff"]), tz=timezone.utc).astimezone(LOCAL_OFFSET).strftime("%Y%m%d")}/">{mx["fixture"]}</a></li>' for mx in m_list])
    c_html = templates['channel'].replace("{{CHANNEL_NAME}}", ch_name).replace("{{MATCH_LISTING}}", f"<ul>{c_list}</ul>").replace("{{DOMAIN}}", DOMAIN)
    safe_write(f"channel/{c_slug}/index.html", c_html)

# 5d. Sitemap
sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join([f'<url><loc>{u}</loc></url>' for u in set(sitemap_urls)]) + '</urlset>'
safe_write("sitemap.xml", sitemap)
print("🏁 Done.")

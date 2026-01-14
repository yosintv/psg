import json, os
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))
page_tpl = env.get_template("page.html")
index_tpl = env.get_template("index.html")

with open("keywords.json", encoding="utf-8") as f:
    data = json.load(f)

os.makedirs("docs", exist_ok=True)
os.makedirs("docs/static", exist_ok=True)

# Generate index
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(index_tpl.render(
        title="無料パスワード生成 | Pasuwado Seisei",
        description="日本語対応の安全なパスワード生成ツール"
    ))

count = 0
for base in data["base_keywords"]:
    for length in data["length_keywords"]:
        for char in data["character_types"]:
            slug = f"{base}-{length}-{char}".replace(" ", "-")
            path = f"docs/{slug}.html"

            html = page_tpl.render(
                title=f"{base} {length} {char}",
                description=f"{length}の{base}を{char}で安全に生成",
                h1=f"{base}（{length}・{char}）",
                intro=f"{length}の{base}を{char}で作成できます。",
                explanation="本ツールはブラウザ内で安全にパスワードを生成します。",
                length=int(length.replace("文字",""))
            )

            with open(path, "w", encoding="utf-8") as f:
                f.write(html)

            count += 1

print(f"Generated {count} pages")

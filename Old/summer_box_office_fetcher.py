# summer_box_office_fetcher.py

import csv
import re
from decimal import Decimal
import requests
from bs4 import BeautifulSoup

BOX_OFFICE_URL = (
    "https://www.the-numbers.com/"
    "box-office-records/domestic/all-movies/"
    "cumulative/released-in-2025"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

def normalize(title: str) -> str:
    return re.sub(r'[^a-z0-9]', '', title.lower())

def load_summer_list(csv_path="summer_movies.csv"):
    """
    Reads your CSV—one column of titles (with or without header).
    Strips any trailing parentheses (e.g. "Thunderbolts* (Wide)").
    Also lops off a leading BOM if present on the first line.
    """
    titles = []
    import csv, re

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first and first[0].strip():
            raw = first[0].lstrip('\ufeff').strip()
            # strip trailing "(…)"
            clean = re.sub(r"\s*\(.*\)$", "", raw).strip()
            if clean.lower() not in ("movie", "title"):
                titles.append(clean)

        for row in reader:
            if not row or not row[0].strip():
                continue
            raw = row[0].strip()
            clean = re.sub(r"\s*\(.*\)$", "", raw).strip()
            titles.append(clean)

    return titles


def fetch_box_office_data():
    resp = requests.get(BOX_OFFICE_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = None
    for tbl in soup.find_all("table"):
        hdrs = [th.get_text(strip=True) for th in tbl.select("thead th")]
        if "Rank" in hdrs:
            table = tbl
            break
    if not table:
        raise RuntimeError("Box‑office table not found.")

    rows = []
    for tr in table.select("tbody tr"):
        cols = tr.find_all("td")
        if len(cols) < 5:
            continue
        title = cols[1].get_text(strip=True)
        gross_txt = cols[3].get_text(strip=True).replace("$","").replace(",","")
        try:
            gross = Decimal(gross_txt)
        except:
            continue
        rows.append((title, gross))
    return rows

def get_top_10_summer_movies(csv_path="summer_movies.csv", debug=False):
    # 1) load and normalize your CSV list
    raw = load_summer_list(csv_path)
    norm_map = { normalize(t): t for t in raw }
    if debug:
        print(f"[DEBUG] Loaded {len(raw)} raw titles from '{csv_path}':")
        for t in raw[:10]:
            print("   ", t)
        print(f"[DEBUG] Norm‑map keys (first 10): {list(norm_map.keys())[:10]}")
        print()

    # 2) scrape the cumulative chart
    data = fetch_box_office_data()
    if debug:
        print(f"[DEBUG] Scraped {len(data)} rows from box‑office chart.")
        print("  First 20 scraped rows:")
        for title, gross in data[:20]:
            key = normalize(title)
            print(f"   '{title}' → norm '{key}', in list? {key in norm_map}")
        print()

    # 3) match only your summer titles
    matched = []
    for title, gross in data:
        key = normalize(title)
        if key in norm_map:
            matched.append({"title": norm_map[key], "gross": gross})

    # 4) sort & slice top 10
    matched.sort(key=lambda x: x["gross"], reverse=True)
    top10 = matched[:10]

    if debug:
        print(f"[DEBUG] Matched {len(matched)} of your titles; Top 10 is:")
        for i, m in enumerate(top10, 1):
            print(f"  {i}. {m['title']} — ${m['gross']:,}")
        print()

    return top10

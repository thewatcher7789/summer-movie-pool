import csv
import re
from decimal import Decimal
from datetime import datetime, date
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

# ------------------------------
# Normalization helpers
# ------------------------------
def normalize_title(title: str) -> str:
    """Lowercase and strip non a-z0-9."""
    return re.sub(r'[^a-z0-9]', '', str(title).lower())

# Alias retained for existing imports in summer_pool.py
def normalize(s: str) -> str:
    return normalize_title(s)

# ------------------------------
# URLs & Headers
# ------------------------------
BOX_OFFICE_URL = (
    "https://www.the-numbers.com/"
    "box-office-records/domestic/all-movies/"
    "cumulative/released-in-2025"
)

TOP_GROSSING_YEAR_URL = "https://www.the-numbers.com/market/2025/top-grossing-movies"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

# ------------------------------
# Your local summer list
# ------------------------------
def load_summer_list(csv_path="summer_movies.csv"):
    """
    Reads your CSV—one title per row (header optional).
    Strips trailing parentheses (e.g. 'Thunderbolts* (Wide)').
    Removes UTF-8 BOM if present.
    """
    titles = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        rdr = csv.reader(f)
        first = next(rdr, None)
        if first and first[0].strip():
            raw = first[0].lstrip('\ufeff').strip()
            clean = re.sub(r"\s*\(.*\)$", "", raw).strip()
            if clean.lower() not in ("movie", "title"):
                titles.append(clean)
        for row in rdr:
            if not row or not row[0].strip():
                continue
            raw = row[0].strip()
            clean = re.sub(r"\s*\(.*\)$", "", raw).strip()
            titles.append(clean)
    return titles

# ------------------------------
# Cumulative domestic by title (year page)
# ------------------------------
# --- Add/replace this helper somewhere near your other helpers ---
def normalize_distributor(name: str) -> str:
    """
    Canonicalize distributor names so variants roll up to the same bucket.
    """
    if not name:
        return "Unknown"
    n = name.strip()

    # Common normalizations
    mapping = {
        "Walt Disney Studios Motion Pictures": "Walt Disney",
        "Walt Disney Pictures": "Walt Disney",
        "Disney": "Walt Disney",
        "Buena Vista": "Walt Disney",

        "Warner Bros. Pictures": "Warner Bros.",
        "Warner Bros": "Warner Bros.",
        "Warner Brothers": "Warner Bros.",

        "Universal Pictures": "Universal",
        "Universal Pictures Distribution": "Universal",
        "Focus Features": "Universal",   # if you want Focus to roll up to Universal, keep this

        "Sony Pictures Releasing": "Sony Pictures",
        "Sony Pictures Entertainment (SPE)": "Sony Pictures",
        "Sony": "Sony Pictures",
        "TriStar Pictures": "Sony Pictures",  # optional roll-up
        "Columbia Pictures": "Sony Pictures", # optional roll-up

        "Paramount Pictures": "Paramount Pictures",
        "Paramount": "Paramount Pictures",

        "Lionsgate": "Lionsgate",
        "Lions Gate Films": "Lionsgate",

        "A24 Films": "A24",
        "A24 Distribution": "A24",

        "20th Century Studios": "Walt Disney",  # if you want 20th to count under Disney
        "Searchlight Pictures": "Walt Disney",  # same, optional roll-up

        # Add more house rules as needed…
    }

    return mapping.get(n, n)

def fetch_box_office_data():
    """
    Scrape the year-2025 cumulative domestic chart.
    Returns list of (title, gross) where gross is Decimal.
    """
    resp = requests.get(BOX_OFFICE_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = None
    for tbl in soup.find_all("table"):
        hdrs = [th.get_text(strip=True) for th in tbl.select("thead th")]
        if "Rank" in hdrs and "Movie" in hdrs:
            table = tbl
            break
    if not table:
        raise RuntimeError("Box-office table not found.")

    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        title = tds[1].get_text(strip=True)
        gross_txt = tds[3].get_text(strip=True).replace("$", "").replace(",", "")
        try:
            gross = Decimal(gross_txt)
        except:
            continue
        rows.append((title, gross))
    return rows

def get_top_10_summer_movies(csv_path="summer_movies.csv", debug=False):
    """
    Intersect the scraped year cumulative chart with your curated summer list,
    then return top 10 by domestic gross.
    """
    # 1) load & normalize your CSV list
    raw_titles = load_summer_list(csv_path)
    norm_map = { normalize_title(t): t for t in raw_titles }
    if debug:
        print(f"[DEBUG] Loaded {len(raw_titles)} raw titles from '{csv_path}':")
        for t in raw_titles[:10]:
            print("   ", t)
        print(f"[DEBUG] Norm-map keys (first 10): {list(norm_map.keys())[:10]}\n")

    # 2) scrape the cumulative chart
    data = fetch_box_office_data()
    if debug:
        print(f"[DEBUG] Fetched {len(data)} total box-office entries")
        for t, g in data[:20]:
            print(f"   '{t}' → in list? {normalize_title(t) in norm_map}")
        print()

    # 3) match only your summer titles
    matched = []
    for title, gross in data:
        key = normalize_title(title)
        if key in norm_map:
            matched.append({"title": norm_map[key], "gross": gross})

    matched.sort(key=lambda x: x["gross"], reverse=True)
    top10 = matched[:10]

    if debug:
        print(f"[DEBUG] Matched {len(matched)} of your titles; Top 10 is:")
        for i, m in enumerate(top10, 1):
            print(f"  {i}. {m['title']} — ${m['gross']:,}")
        print()

    return top10

# ------------------------------
# Year list w/ Release Date & Distributor (for distributor totals)
# ------------------------------
def _parse_us_date(s: str) -> date | None:
    """
    Parse strings like 'May 3, 2025' → date; return None if can't parse.
    """
    s = (s or "").strip()
    try:
        return datetime.strptime(s, "%B %d, %Y").date()
    except Exception:
        return None

def fetch_year_movies_with_distributors(debug: bool = False):
    """
    Scrape https://www.the-numbers.com/market/2025/top-grossing-movies
    Return a list of dicts: {movie, release (datetime|None), dist, gross}
    Tolerant to odd rows; never silently drops an entire row unless it's empty.
    """
    import re
    from datetime import datetime
    import requests
    from bs4 import BeautifulSoup

    YEAR_URL = "https://www.the-numbers.com/market/2025/top-grossing-movies"
    HEADERS = {"User-Agent": "Mozilla/5.0"}

    def parse_dollar_safe(s: str) -> int:
        try:
            # remove everything except digits
            return int(re.sub(r"[^\d]", "", s or "") or "0")
        except Exception:
            return 0

    def parse_date_safe(s: str):
        if not s:
            return None
        s = s.strip()
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        return None  # tolerate unparseable

    # Fetch
    resp = requests.get(YEAR_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the correct table by headers (be flexible)
    tables = soup.find_all("table")
    if debug:
        print(f"[DEBUG] Found {len(tables)} tables on yearly page.")

    chosen = None
    colmap = None

    def norm_header(h: str) -> str:
        return (h or "").strip().lower().replace(" ", "").replace("\xa0", "")

    # Look for headers that include Movie, ReleaseDate, Distributor, Gross
    for idx, t in enumerate(tables, start=1):
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if not headers:
            continue
        nh = [norm_header(h) for h in headers]
        if debug:
            print(f"[DEBUG] Table {idx} headers: {headers}")

        # Accept both "Release Date" and "ReleaseDate"; "2025 Gross" may appear
        if any("movie" in h for h in nh) and \
           any("release" in h for h in nh) and \
           any("distributor" in h for h in nh) and \
           any(("gross" in h) or ("2025gross" in h) for h in nh):
            chosen = t
            # Build a column index map
            def find_idx(key_opts):
                for k in key_opts:
                    if k in nh:
                        return nh.index(k)
                return None

            colmap = {
                "movie": find_idx(["movie"]),
                "release": find_idx(["releasedate", "release", "openingdate"]),
                # some tables show "2025 Gross", some just "Gross"
                "gross": find_idx(["2025gross", "gross"]),
                "dist": find_idx(["distributor"]),
            }
            if debug:
                print("[DEBUG] Chosen yearly table with headers:", headers)
                print("[DEBUG] Column map:", colmap)
            break

    if chosen is None or colmap is None or any(v is None for v in colmap.values()):
        raise RuntimeError("Year top-grossing table not found.")

    # Parse rows tolerantly
    rows_out = []
    for tr in chosen.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        try:
            # Extract safe text per column map
            def txt(i):
                if i is None or i >= len(tds):
                    return ""
                return tds[i].get_text(strip=True)

            movie = txt(colmap["movie"])
            if not movie:
                continue

            release_raw = txt(colmap["release"])
            release_dt = parse_date_safe(release_raw)

            dist_raw = txt(colmap["dist"])
            # Distributors sometimes appear as "Studio A / Studio B" etc.
            # We'll store the raw string and normalize / split during aggregation.
            gross_val = parse_dollar_safe(txt(colmap["gross"]))

            rows_out.append({
                "movie": movie,
                "release": release_dt,   # can be None
                "dist": dist_raw or "Unknown",
                "gross": gross_val
            })
        except Exception:
            # swallow row-level errors so we don't lose the whole table
            continue

    if debug:
        print(f"[DEBUG] Parsed {len(rows_out)} rows from yearly list (after tolerant parsing).")

    return rows_out
def get_top_distributors_for_summer(limit: int = 5, debug: bool = False):
    """
    Build Top distributors for summer window by summing grosses of movies released
    between May 1 and Aug 31, inclusive. Returns list of (distributor, total_gross).
    """
    from datetime import datetime
    import re
    ALL = fetch_year_movies_with_distributors(debug=debug)

    # Summer window
    start = datetime(2025, 5, 1)
    end   = datetime(2025, 9, 1)  # exclusive of Sep 1; change to Sep 1 inclusive if desired

    def in_summer(dt):
        if dt is None:
            return False
        return (dt >= start) and (dt < end)

    # Aggregate
    totals = {}
    splitter = re.compile(r"\s*(?:/|&|,| and )\s*", re.IGNORECASE)

    for row in ALL:
        if not in_summer(row.get("release")):
            continue
        gross = int(row.get("gross") or 0)
        if gross <= 0:
            continue

        # Split multi-distributor rows: "Warner Bros. / Legendary" etc.
        for part in splitter.split(row.get("dist") or ""):
            if not part.strip():
                continue
            dist = normalize_distributor(part)
            totals[dist] = totals.get(dist, 0) + gross

    # Sort + limit
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ranked = ranked[:limit]

    if debug:
        print("\n[DEBUG] Top distributors (summer window):")
        for i, (d, g) in enumerate(ranked, 1):
            print(f"  {i}. {d} — ${g:,}")

    return ranked

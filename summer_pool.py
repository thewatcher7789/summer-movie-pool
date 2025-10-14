#!/usr/bin/env python3
import argparse
import csv
import sys

from summer_box_office_fetcher import (
    get_top_10_summer_movies,
    get_top_distributors_for_summer,
    normalize as normalize_title,
)

# === MANUAL monthly opening-weekend winners ===
# (You can update as each month concludes.)
MONTHLY_WINNERS = {
    "May":    "Lilo & Stitch",
    "June":   "How to Train Your Dragon",
    "July":   "Superman",
    "August": "Weapons",
}

# Points for distributor rank guesses
DIST_RANK_POINTS = {1: 5, 2: 3, 3: 1}

# ---------------------------------------------
# Entries loader (backwards compatible)
# ---------------------------------------------
DIST_HEADER_VARIANTS = [
    ("Dist 1", "Dist 2", "Dist 3"),
    ("Dist1", "Dist2", "Dist3"),
    ("Distributor 1", "Distributor 2", "Distributor 3"),
    ("Top Distributor 1", "Top Distributor 2", "Top Distributor 3"),
]
def normalize_dist(name: str) -> str:
    if not name:
        return ""
    n = name.strip()
    # common unifications to keep buckets consistent
    mapping = {
        "Walt Disney Studios Motion Pictures": "Walt Disney",
        "Disney": "Walt Disney",
        "The Walt Disney Studios": "Walt Disney",

        "Warner Bros. Pictures": "Warner Bros.",
        "Warner Bros": "Warner Bros.",
        "Warner Bros. Discovery": "Warner Bros.",

        "Universal Pictures": "Universal",

        "Sony Pictures Releasing": "Sony Pictures",
        "Columbia Pictures": "Sony Pictures",

        "Paramount": "Paramount Pictures",
    }
    return mapping.get(n, n)


def rank_distributors_from_bo(bo_rows, summer_norm_set, debug=False):
    """
    Sum grosses per distributor using the SAME box-office rows used for Top 10,
    restricted to titles that are in the summer CSV list.
    bo_rows: list of dicts with keys: 'title', 'gross', 'distributor'
    summer_norm_set: set of normalized titles from summer_movies.csv
    """
    from collections import defaultdict
    totals = defaultdict(int)
    kept_examples = []  # for debug

    for row in bo_rows:
        t = row.get('title', '')
        if not t:
            continue
        if normalize_title(t) not in summer_norm_set:
            continue

        g = row.get('gross', 0) or 0
        d = normalize_dist(row.get('distributor', ''))

        if not d:
            continue

        totals[d] += int(g)
        if debug and len(kept_examples) < 8:
            kept_examples.append((t, d, g))

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

    if debug:
        print("\n[DEBUG] Distributor examples included (title, dist, gross):")
        for t,d,g in kept_examples:
            print(f"   - {t} | {d} | ${g:,}")

        print("\n[DEBUG] Top distributors (computed from box-office table + summer CSV):")
        for i,(d,amt) in enumerate(ranked[:10], 1):
            print(f"  {i}. {d} — ${amt:,}")

    return ranked
def _pick_existing_headers(header_row, variants):
    """Return the first variant tuple fully present in the header row."""
    lower = [h.lower() for h in header_row]
    for trio in variants:
        if all(h.lower() in lower for h in trio):
            return trio
    return None

def load_entries(path, debug=False):
    """
    Expected columns:
      Name, Pick 1 .. Pick 10, May, June, July, August,
      plus distributor guesses (Dist 1/2/3 or Distributor 1/2/3, etc.)
    """
    entries = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            dist_headers = _pick_existing_headers(header, DIST_HEADER_VARIANTS)

            for row in reader:
                name  = (row.get("Name") or "").strip()
                picks = [(row.get(f"Pick {i}") or "").strip() for i in range(1, 11)]
                monthly = {m: (row.get(m) or "").strip() for m in MONTHLY_WINNERS}

                # Distributor guesses (try to be flexible)
                dists = ["", "", ""]
                if dist_headers:
                    dists = [(row.get(dist_headers[0]) or "").strip(),
                             (row.get(dist_headers[1]) or "").strip(),
                             (row.get(dist_headers[2]) or "").strip()]

                entries.append({
                    "name": name,
                    "picks": picks,
                    "monthly": monthly,
                    "dists": dists,  # [first, second, third]
                })
    except FileNotFoundError:
        sys.exit(f"Entries file not found: {path}")

    if debug:
        print(f"[DEBUG] Loaded {len(entries)} entries from '{path}'")
    return entries

# ---------------------------------------------
# Scoring
# ---------------------------------------------
def score_entry(picks, actual_titles, monthly_guess, dist_guesses, dist_rankings):
    """
    Picks:
      +1 if anywhere in top 10
      +N bonus if in exact position N
    Monthly opening winners:
      +3 for each correct month
    Distributors:
      if dist_guesses[0] == 1st place → +5
      if dist_guesses[1] == 2nd place → +3
      if dist_guesses[2] == 3rd place → +1
    """
    total = 0

    # Top 10 placement (+1) and exact rank bonus (+N)
    for idx, pick in enumerate(picks, start=1):
        npick = normalize_title(pick)
        for pos, real in enumerate(actual_titles, start=1):
            if npick == normalize_title(real):
                total += 1
                if pos == idx:
                    total += pos
                break

    # Monthly +3
    for month, winner in MONTHLY_WINNERS.items():
        guess = (monthly_guess.get(month) or "")
        if winner and normalize_title(guess) == normalize_title(winner):
            total += 3

    # Distributor rank bonuses
    # dist_rankings is a mapping: distributor → rank (1..N)
    for wanted_rank, guess in enumerate(dist_guesses, start=1):
        if not guess:
            continue
        gnorm = normalize_title(guess)
        for dist, rank in dist_rankings.items():
            if normalize_title(dist) == gnorm and rank == wanted_rank:
                total += DIST_RANK_POINTS.get(wanted_rank, 0)
                break

    return total

# ---------------------------------------------
# Output
# ---------------------------------------------
def write_csv(path, scored, top10, top_dists):
    """
    CSV with three blocks:
      1) Top 10 Summer Movies
      2) Top 5 Distributors
      3) Leaderboard
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        # Top 10
        w.writerow(["# Top 10 Summer Movies", "Domestic Gross"])
        for i, m in enumerate(top10, start=1):
            w.writerow([f"{i}. {m['title']}", f"${m['gross']:,}"])
        w.writerow([])

        # Distributors
        w.writerow(["# Top 5 Distributors (May–Aug releases)", "Sum Domestic Gross"])
        for i, (d, g) in enumerate(top_dists, start=1):
            w.writerow([f"{i}. {d}", f"${g:,}"])
        w.writerow([])

        # Leaderboard
        w.writerow(["Rank", "Name", "Score"])
        for i, e in enumerate(scored, start=1):
            w.writerow([i, e["name"], e["score"]])

def write_html(results, top10, monthly_winners, top_dists, path="leaderboard.html"):
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1'>",
        "  <title>Summer Movie Pool Leaderboard</title>",
        "  <style>",
        "    body { font-family: 'Segoe UI', Tahoma, sans-serif; background:#f4f7fa; margin:0; padding:20px; color:#333; }",
        "    .container { max-width:900px; margin:auto; background:#fff; padding:20px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.1); }",
        "    h1 { text-align:center; margin:0 0 1rem; color:#222; }",
        "    table { width:100%; border-collapse:collapse; margin: 1.25rem 0 2rem; }",
        "    thead th { background:#005f73; color:#fff; padding:12px; text-align:left; }",
        "    tbody tr:nth-child(even){ background:#e0fbfc; }",
        "    tbody tr:hover{ background:#94d2bd; }",
        "    td,th { padding:10px; border-bottom:1px solid #ccc; }",
        "    .rank-col { width:50px; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class='container'>",
        "    <h1>Current Top 10 Summer Movies</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Movie</th><th>Gross</th></tr></thead>",
        "      <tbody>",
    ]
    for i, m in enumerate(top10, 1):
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{m['title']}</td><td>${m['gross']:,}</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        "",
        "    <h1>Top 5 Distributors (May–Aug releases)</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Distributor</th><th>Total Domestic</th></tr></thead>",
        "      <tbody>",
    ]
    for i, (d, g) in enumerate(top_dists, 1):
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{d}</td><td>${g:,}</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        "",
        "    <h1>Monthly Opening-Weekend Winners (+3 pts each)</h1>",
        "    <table>",
        "      <thead><tr><th>Month</th><th>Winner</th><th>Bonus</th></tr></thead>",
        "      <tbody>",
    ]
    for month in ("May", "June", "July", "August"):
        winner = monthly_winners.get(month)
        if winner:
            html.append(f"        <tr><td>{month}</td><td>{winner}</td><td>+3</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        "",
        "    <h1>Pool Leaderboard</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Name</th><th>Score</th></tr></thead>",
        "      <tbody>",
    ]
    for i, r in enumerate(results, 1):
        name  = r.get("name") or r.get("Name", "—")
        score = r.get("score") or r.get("Score", 0)
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{name}</td><td>{score}</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        "  </div>",
        "</body>",
        "</html>",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

# ---------------------------------------------
# Main
# ---------------------------------------------
def main():
    p = argparse.ArgumentParser(prog="Summer Movie Pool Leaderboard")
    p.add_argument("--entries", required=True,
                   help="CSV of Name, Pick1..Pick10, May..Aug, plus distributor columns")
    p.add_argument("--csv", dest="csv_path", required=True,
                   help="CSV of all summer releases (column Title)")
    p.add_argument("--debug", action="store_true", help="Verbose logging")
    args = p.parse_args()

    # 1) Top 10 (from your curated list)
    top10 = get_top_10_summer_movies(csv_path=args.csv_path, debug=args.debug)
    if not top10:
        sys.exit("No summer top 10 found—check your fetcher.")
    actual_titles = [m["title"] for m in top10]

    # 2) Top distributors
    top_dists = get_top_distributors_for_summer(limit=5, debug=args.debug)
    # map distributor → rank
    dist_rankings = {dist: i for i, (dist, _sum) in enumerate(top_dists, start=1)}

    # 3) Score everyone
    entries = load_entries(args.entries, debug=args.debug)
    scored = []
    for e in entries:
        pts = score_entry(
            picks=e["picks"],
            actual_titles=actual_titles,
            monthly_guess=e["monthly"],
            dist_guesses=e["dists"],
            dist_rankings=dist_rankings,
        )
        scored.append({"name": e["name"], "score": pts})
    scored.sort(key=lambda x: (-x["score"], x["name"]))

    # 4) Console output
    print("\nCurrent Top 10 Summer Movies:")
    for i, m in enumerate(top10, 1):
        print(f"  {i}. {m['title']} — ${m['gross']:,}")

    print("\nTop 5 Distributors (May–Aug releases):")
    for i, (d, g) in enumerate(top_dists, 1):
        print(f"  {i}. {d} — ${g:,}")

    print("\nMonthly Opening-Weekend Winners (+3 pts each):")
    for month, winner in MONTHLY_WINNERS.items():
        if winner:
            print(f"  {month}: {winner}")

    print("\nPool Leaderboard:")
    for e in scored:
        print(f"  {e['name']}: {e['score']} pts")

    # 5) Export
    write_csv("leaderboard.csv", scored, top10, top_dists)
    write_html(scored, top10, MONTHLY_WINNERS, top_dists, path="leaderboard.html")
    print("\nSaved leaderboard.csv and leaderboard.html")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import csv
import sys
from summer_box_office_fetcher import get_top_10_summer_movies, normalize as normalize_title

# === MANUAL MONTHLY OPENING-WEEKEND WINNERS ===
# Fill in as each month’s winner is known; May is done.
MONTHLY_WINNERS = {
    'May':    'Lilo & Stitch',
    'June':   'How to Train Your Dragon',
    'July':   'Superman',
    'August': None,
}

def load_entries(path):
    """
    Load each player’s picks and monthly guesses from a CSV with columns:
      Name, Pick 1…Pick 10, May, June, July, August
    """
    entries = []
    try:
        with open(path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name    = row['Name'].strip()
                picks   = [row.get(f'Pick {i}','').strip() for i in range(1,11)]
                monthly = {month: row.get(month, '').strip() 
                           for month in MONTHLY_WINNERS}
                entries.append({
                    'name':    name,
                    'picks':   picks,
                    'monthly': monthly
                })
    except FileNotFoundError:
        sys.exit(f"Entries file not found: {path}")
    return entries

def score_entry(picks, actual_titles, monthly_guess):
    """
    For each pick:
      • +1 if it’s anywhere in top 10
      • +N if it’s exactly in position N (bonus points = that rank)
    Plus +3 for each correct monthly‐opening guess.
    """
    total = 0
    for idx, pick in enumerate(picks, start=1):
        npick = normalize_title(pick)
        for pos, real in enumerate(actual_titles, start=1):
            if npick == normalize_title(real):
                total += 1
                if pos == idx:
                    total += pos
                break

    # Monthly bonuses
    for month, winner in MONTHLY_WINNERS.items():
        guess = monthly_guess.get(month, '')
        if winner and normalize_title(guess) == normalize_title(winner):
            total += 3

    return total

def write_csv(path, scored, top10):
    """
    Write out a CSV with two blocks:
      1) Top 10 Summer Movies + gross
      2) Leaderboard: Rank,Name,Score
    """
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        # Top10 block
        w.writerow(['# Top 10 Summer Movies','Domestic Gross'])
        for i, m in enumerate(top10, start=1):
            w.writerow([f"{i}. {m['title']}", f"${m['gross']:,}"])
        w.writerow([])  # blank line
        # Leaderboard block
        w.writerow(['Rank','Name','Score'])
        for i, e in enumerate(scored, start=1):
            w.writerow([i, e['name'], e['score']])

def write_html(results, top10, monthly_winners, path="leaderboard.html"):
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1'>",
        "  <title>Summer Movie Pool Leaderboard</title>",
        "  <style>",
        "    /* Page & Container */",
        "    body {",
        "      font-family: 'Segoe UI', Tahoma, sans-serif;",
        "      background-color: #f4f7fa;",
        "      margin: 0;",
        "      padding: 20px;",
        "      color: #333;",
        "    }",
        "    .container {",
        "      max-width: 800px;",
        "      margin: auto;",
        "      background: #fff;",
        "      padding: 20px;",
        "      box-shadow: 0 2px 8px rgba(0,0,0,0.1);",
        "      border-radius: 8px;",
        "    }",
        "    h1 {",
        "      text-align: center;",
        "      margin-bottom: 1rem;",
        "      color: #222;",
        "    }",
        "",
        "    /* Tables */",
        "    table {",
        "      width: 100%;",
        "      border-collapse: collapse;",
        "      margin-bottom: 2rem;",
        "    }",
        "    thead th {",
        "      background-color: #005f73;",
        "      color: #fff;",
        "      padding: 12px;",
        "      text-align: left;",
        "    }",
        "    tbody tr:nth-child(even) {",
        "      background-color: #e0fbfc;",
        "    }",
        "    tbody tr:hover {",
        "      background-color: #94d2bd;",
        "    }",
        "    td, th {",
        "      padding: 10px;",
        "      border-bottom: 1px solid #ccc;",
        "    }",
        "    .rank-col {",
        "      width: 50px;",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class='container'>",
        "    <h1>Current Top 10 Summer Movies</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Movie</th><th>Gross</th></tr></thead>",
        "      <tbody>"
    ]
    # Top 10 Summer Movies
    for i, m in enumerate(top10, 1):
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{m['title']}</td><td>${m['gross']:,}</td></tr>")

    # Monthly Winners
    html += [
        "      </tbody>",
        "    </table>",
        "",
        "    <h1>Monthly Opening-Weekend Winners (+3 pts each)</h1>",
        "    <table>",
        "      <thead><tr><th>Month</th><th>Winner</th><th>Bonus</th></tr></thead>",
        "      <tbody>"
    ]
    for month in ("May", "June", "July", "August"):
        winner = monthly_winners.get(month)
        if winner:
            html.append(f"        <tr><td>{month}</td><td>{winner}</td><td>+3</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        ""
    ]

    # Pool Leaderboard
      # … after your top10 table …
    html += [
        "    <h1>Pool Leaderboard</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Name</th><th>Score</th></tr></thead>",
        "      <tbody>"
    ]
    for i, r in enumerate(results, 1):
        # support either {'Name','Score'} or {'name','score'}
        name  = r.get('Name', r.get('name', '—'))
        score = r.get('Score', r.get('score', 0))
        html.append(
            f"        <tr>"
            f"<td class='rank-col'>{i}</td>"
            f"<td>{name}</td>"
            f"<td>{score}</td>"
            f"</tr>"
        )
    html += [
        "      </tbody>",
        "    </table>",
        "  </div>",
        "</body>",
        "</html>"
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))


def main():
    p = argparse.ArgumentParser(prog="Summer Movie Pool Leaderboard")
    p.add_argument('--entries', required=True,
                   help="CSV of Name,Pick 1…10,May,June,July,August")
    p.add_argument('--csv', dest='csv_path', required=True,
                   help="CSV of all summer releases (column Title)")
    p.add_argument('--debug', action='store_true',
                   help="Show debug logging")
    args = p.parse_args()

    # 1) Fetch your top 10 summer movies (handles scraping & filtering) :contentReference[oaicite:5]{index=5}
    top10 = get_top_10_summer_movies(
        csv_path=args.csv_path,
        debug=args.debug
    )
    if not top10:
        sys.exit("No summer top 10 found—check your fetcher.")

    # 2) Load & score everyone
    entries       = load_entries(args.entries)
    actual_titles = [m['title'] for m in top10]

    scored = []
    if args.debug:
        print(f"[DEBUG] Actual Top 10 titles: {actual_titles}")
    for e in entries:
        s = score_entry(e['picks'], actual_titles, e['monthly'])
        scored.append({'name': e['name'], 'score': s})
        if args.debug:
            print(f"[DEBUG] {e['name']} → {s} pts")

    # 3) Sort descending by score, then name
    scored.sort(key=lambda x: (-x['score'], x['name']))

    # --- Console output ---
    print("\nCurrent Top 10 Summer Movies:")
    for i, m in enumerate(top10, 1):
        print(f"  {i}. {m['title']} — ${m['gross']:,}")

    print("\nMonthly Opening-Weekend Winners (+3 pts each):")
    for month, winner in MONTHLY_WINNERS.items():
        if winner:
            print(f"  {month}: {winner}")

    print("\nPool Leaderboard:")
    for e in scored:
        print(f"  {e['name']}: {e['score']} pts")

    # --- Export ---
    write_csv('leaderboard.csv', scored, top10)
    write_html(scored, top10, MONTHLY_WINNERS, path='leaderboard.html')
    print("\nSaved leaderboard.csv and leaderboard.html")

if __name__ == '__main__':
    main()

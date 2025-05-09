# summer_pool.py

import csv
import argparse
from summer_box_office_fetcher import get_top_10_summer_movies

def load_entries(path="entries.csv"):
    entries = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Name"]
            picks = [row[f"Pick {i}"].strip() for i in range(1,11)]
            entries.append({"name": name, "picks": picks})
    return entries

def score_entry(picks, actual):
    total = 0
    for idx, pick in enumerate(picks, start=1):
        for pos, m in enumerate(actual, start=1):
            if pick == m["title"]:
                total += pos if pos == idx else 1
                break
    return total

def write_csv(results, top10, path="leaderboard.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # write top 10 block
        w.writerow(["# Top 10 Summer Movies", "Domestic Gross"])
        for m in top10:
            w.writerow([m["title"], f"${m['gross']:,}"])
        w.writerow([])  # blank line
        # write entries leaderboard
        w.writerow(["Rank","Name","Score"])
        for i,r in enumerate(results,1):
            w.writerow([i, r["name"], r["score"]])

def write_html(results, top10, path="leaderboard.html"):
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
        "    <h1>Current Top 10 Summer Movies</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Movie</th><th>Gross</th></tr></thead>",
        "      <tbody>"
    ]
    for i, m in enumerate(top10, 1):
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{m['title']}</td><td>${m['gross']:,}</td></tr>")
    html += [
        "      </tbody>",
        "    </table>",
        "",
        "    <h1>Pool Leaderboard</h1>",
        "    <table>",
        "      <thead><tr><th class='rank-col'>#</th><th>Name</th><th>Score</th></tr></thead>",
        "      <tbody>"
    ]
    for i, r in enumerate(results, 1):
        html.append(f"        <tr><td class='rank-col'>{i}</td><td>{r['name']}</td><td>{r['score']}</td></tr>")
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
    p = argparse.ArgumentParser()
    p.add_argument("--entries", default="entries.csv")
    p.add_argument("--csv",     default="summer_movies.csv")
    p.add_argument("--debug",   action="store_true")
    args = p.parse_args()

    # fetch top10 with grosses
    top10 = get_top_10_summer_movies(csv_path=args.csv, debug=args.debug)
    if not top10:
        print("No summer top 10 found—check your fetcher.")
        return

    # show them in console
    print("\nCurrent Top 10 Summer Movies:")
    for i,m in enumerate(top10,1):
        print(f" {i:2d}. {m['title']} — ${m['gross']:,}")

    # load & score entries
    entries = load_entries(args.entries)
    results = []
    for e in entries:
        s = score_entry(e["picks"], top10)
        results.append({"name": e["name"], "score": s})
    results.sort(key=lambda x: x["score"], reverse=True)

    # console leaderboard
    print("\nPool Leaderboard:")
    for r in results:
        print(f" {r['name']}: {r['score']} points")

    # write files
    write_csv(results, top10)
    write_html(results, top10)
    print("\nSaved leaderboard.csv and leaderboard.html")

if __name__=="__main__":
    main()

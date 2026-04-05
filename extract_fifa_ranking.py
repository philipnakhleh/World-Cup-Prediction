"""
FIFA Ranking Extractor
----------------------
Parses an HTML file containing a FIFA world ranking table and extracts:
  - fifa_rank      : the rank number from <h3> inside .custom-rank-cell_rankNumber__RORLl
  - team           : team name from <a> inside .custom-team-cell_teamName__c_tEs
  - country_code   : parsed from the href of the same <a> tag  (e.g. /fifa-world-ranking/FRA -> FRA)
  - fifa_points    : points from <span> inside .custom-points-cell_points__Lt6_7
  - confederation  : extracted from the <a> href or a sibling element if present

Usage:
    python extract_fifa_ranking.py --input ranking.html --output fifa_ranking.csv

Dependencies:
    pip install beautifulsoup4 lxml
"""

import csv
import re
import argparse
from pathlib import Path
from bs4 import BeautifulSoup


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_country_code(href: str) -> str:
    """Extract 3-letter country code from href like /fifa-world-ranking/FRA?gender=men"""
    if not href:
        return ""
    # grab the last path segment before any query string
    path = href.split("?")[0]          # strip query
    code = path.rstrip("/").split("/")[-1]   # last segment
    return code.upper()


def extract_confederation(row) -> str:
    """
    Try to find a confederation value inside the <tr>.
    FIFA pages sometimes put it in a separate <td> or as a data attribute.
    Adjust the selector below if your HTML uses a different class name.
    """
    # Attempt 1 – look for a dedicated confederation cell class
    conf_cell = row.find(class_=re.compile(r"confederation", re.I))
    if conf_cell:
        return conf_cell.get_text(strip=True)

    # Attempt 2 – look for an image alt attribute that carries the confederation
    img = row.find("img", alt=re.compile(r"(UEFA|CONMEBOL|CONCACAF|CAF|AFC|OFC)", re.I))
    if img:
        match = re.search(r"(UEFA|CONMEBOL|CONCACAF|CAF|AFC|OFC)", img["alt"], re.I)
        if match:
            return match.group(1).upper()

    # Attempt 3 – look for any text node matching a confederation abbreviation
    row_text = row.get_text(" ")
    match = re.search(r"\b(UEFA|CONMEBOL|CONCACAF|CAF|AFC|OFC)\b", row_text, re.I)
    if match:
        return match.group(1).upper()

    return ""          # not found – leave blank; enrich later if needed


# ── main extractor ────────────────────────────────────────────────────────────

def extract_rows(html_path: str) -> list[dict]:
    html = Path(html_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    results = []

    # Target every expandable data row inside <tbody>
    rows = soup.select("tbody tr.row-even.row-expandable, tbody tr.row-odd.row-expandable")

    # Fallback: if the above yields nothing, grab all <tr> with row-expandable
    if not rows:
        rows = soup.select("tbody tr.row-expandable")

    if not rows:
        print("⚠  No matching <tr> rows found. Check your HTML structure.")
        return results

    for row in rows:
        # ── Rank ──────────────────────────────────────────────────────────────
        rank_tag = row.find("h3", class_=re.compile(r"rankNumber", re.I))
        fifa_rank = rank_tag.get_text(strip=True) if rank_tag else ""

        # ── Team name & country code ──────────────────────────────────────────
        team_link = row.find("a", class_=re.compile(r"teamName", re.I))
        if team_link:
            team        = team_link.get_text(strip=True)
            country_code = parse_country_code(team_link.get("href", ""))
        else:
            team         = ""
            country_code = ""

        # ── FIFA points ───────────────────────────────────────────────────────
        points_cell = row.find("h4", class_=re.compile(r"points", re.I))
        if points_cell:
            span = points_cell.find("span")
            fifa_points = span.get_text(strip=True) if span else points_cell.get_text(strip=True)
        else:
            fifa_points = ""

        # ── Confederation ─────────────────────────────────────────────────────
        confederation = extract_confederation(row)

        results.append({
            "fifa_rank"    : fifa_rank,
            "team"         : team,
            "country_code" : country_code,
            "fifa_points"  : fifa_points,
            "confederation": confederation,
        })

    return results


# ── writer ────────────────────────────────────────────────────────────────────

def save_csv(records: list[dict], output_path: str):
    fieldnames = ["fifa_rank", "team", "country_code", "fifa_points", "confederation"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"✅  Saved {len(records)} rows → {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract FIFA ranking data from HTML to CSV")
    parser.add_argument("--input",  required=True, help="Path to the HTML file")
    parser.add_argument("--output", default="fifa_ranking.csv", help="Output CSV path (default: fifa_ranking.csv)")
    args = parser.parse_args()

    records = extract_rows(args.input)

    if records:
        save_csv(records, args.output)
        # Preview first 5 rows in terminal
        print("\nPreview (first 5 rows):")
        header = f"{'Rank':<6} {'Team':<25} {'Code':<6} {'Points':<10} {'Confederation'}"
        print(header)
        print("-" * len(header))
        for r in records[:5]:
            print(f"{r['fifa_rank']:<6} {r['team']:<25} {r['country_code']:<6} {r['fifa_points']:<10} {r['confederation']}")
    else:
        print("No data extracted. Please check the HTML structure.")

#!/usr/bin/env python3
"""
scrape_885.py — Scrape 885.slovaronline.com (Французско-русский фразеологический словарь)

The dictionary has ~46,210 entries with URLs like:
  https://885.slovaronline.com/23767-le_malheur_des_uns_fait_le_bonheur_des_autres

Strategy:
  1. Fetch the sitemap or index pages to get all entry URLs
  2. For each entry, extract: French idiom, register label, Russian equivalents, examples
  3. Save to SQLite database for use in idiom matching pipeline

Usage:
  python pipeline/scrape_885.py --test          # test on a few known URLs
  python pipeline/scrape_885.py --index         # fetch all entry URLs from index
  python pipeline/scrape_885.py --scrape        # scrape all entries (slow, ~46k pages)
  python pipeline/scrape_885.py --scrape --limit 1000  # scrape first 1000
"""

import re
import time
import sqlite3
import argparse
import requests
from pathlib import Path
from bs4 import BeautifulSoup

PIPELINE_DIR = Path(__file__).parent
DB_PATH      = PIPELINE_DIR / "rf_dict.db"
BASE_URL     = "https://885.slovaronline.com"

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,fr;q=0.8,en;q=0.7',
    'Referer':         'https://885.slovaronline.com/',
    'Cookie':          'pi=HPm+b2mn1HaphUKbSszw2GKgp6ZvbHQqk8M2dhsvIP6ZYR7gnOCoO0z9N8OaNvtZ2c5hugGcS4qHJwK9Dx4Em9UHq4A=; yashr=3823293591779915118',
}

# Known working entry URLs for testing
TEST_URLS = [
    "https://885.slovaronline.com/41172-un_malheur_en_am%C3%A8ne_un_autre",
    "https://885.slovaronline.com/41173-un_malheur_est_sit%C3%B4t_arriv%C3%A9",
    "https://885.slovaronline.com/23767-le_malheur_des_uns_fait_le_bonheur_des_autres",
    "https://885.slovaronline.com/17357-faire_un_malheur",
]


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fr_idiom_gak (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT UNIQUE,
            entry_num       INTEGER,
            fr_idiom        TEXT NOT NULL,
            fr_variants     TEXT,      -- semicolon-separated variant forms
            register        TEXT,      -- prov. fam. fig. etc.
            ru_equivalents  TEXT,      -- semicolon-separated Russian equivalents
            fr_example      TEXT,      -- French example sentence
            ru_example      TEXT,      -- Russian translation of example
            raw_html        TEXT,      -- store raw for reprocessing
            scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# ============================================================
# PARSER
# ============================================================

def parse_entry_page(html: str, url: str) -> dict:
    """Parse a single dictionary entry page."""
    soup = BeautifulSoup(html, 'html.parser')

    result = {
        'url':            url,
        'entry_num':      _extract_entry_num(url),
        'fr_idiom':       '',
        'fr_variants':    '',
        'register':       '',
        'ru_equivalents': '',
        'fr_example':     '',
        'ru_example':     '',
        'raw_html':       html[:5000],  # store first 5000 chars
    }

    # Try to find the main entry content
    # The site structure: title is the French idiom, content has Russian equivalents

    # Method 1: page title
    title = soup.find('h1') or soup.find('title')
    if title:
        title_text = title.get_text().strip()
        # Remove site name suffix if present
        title_text = re.sub(r'\s*[|\-–]\s*.*фразеологический.*$', '', title_text,
                           flags=re.IGNORECASE).strip()
        if title_text:
            result['fr_idiom'] = title_text

    # Method 2: look for the entry content div
    content = (soup.find('div', class_='entry') or
               soup.find('div', class_='word') or
               soup.find('div', class_='content') or
               soup.find('article') or
               soup.find('main'))

    if content:
        text = content.get_text(separator='\n').strip()

        # Extract register label (prov., fam., fig., etc.)
        reg_match = re.search(
            r'\b(prov\.|fam\.|fam\.,?\s*iron\.|fig\.|iron\.|péj\.|vx\.|'
            r'vulg\.|pop\.|arg\.|litt\.|sout\.|euph\.)',
            text, re.IGNORECASE
        )
        if reg_match:
            result['register'] = reg_match.group(1)

        # Extract Russian equivalents — Cyrillic text
        # Usually appears after the French definition/label
        ru_matches = re.findall(
            r'([а-яёА-ЯЁ][а-яёА-ЯЁ\s,;()«»\-–—]+[а-яёА-ЯЁ])',
            text
        )
        if ru_matches:
            # Filter out very short matches and join
            ru_equiv = [m.strip() for m in ru_matches if len(m.strip()) > 5]
            result['ru_equivalents'] = '; '.join(ru_equiv[:5])  # max 5 equivalents

        # Extract French example (italic or in quotes)
        # Usually author name + text in italics
        examples = content.find_all('i') or content.find_all('em')
        if examples:
            ex_texts = [e.get_text().strip() for e in examples if len(e.get_text().strip()) > 20]
            if ex_texts:
                result['fr_example'] = ex_texts[0][:300]

    return result


def _extract_entry_num(url: str) -> int:
    """Extract numeric ID from URL like /17357-faire_un_malheur."""
    m = re.search(r'/(\d+)-', url)
    return int(m.group(1)) if m else 0


# ============================================================
# FETCHER
# ============================================================

def fetch_page(url: str, session: requests.Session,
               retries: int = 3, delay: float = 2.0) -> str | None:
    """Fetch a page with retry logic."""
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                # Rate limited
                wait = delay * (attempt + 1) * 3
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 403:
                print(f"  Blocked (403) — try with browser cookies")
                return None
            else:
                print(f"  HTTP {resp.status_code} for {url}")
                return None
        except Exception as e:
            print(f"  Error: {e} (attempt {attempt+1}/{retries})")
            time.sleep(delay)
    return None


def get_index_urls(session: requests.Session) -> list:
    """
    Get all entry URLs from the dictionary index.
    The site likely has alphabetical index pages.
    """
    urls = []

    # Try the main search/index page
    index_url = f"{BASE_URL}/search"
    html = fetch_page(index_url, session)
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        # Find all entry links
        links = soup.find_all('a', href=re.compile(r'/\d+-'))
        for link in links:
            href = link.get('href', '')
            if href.startswith('/'):
                urls.append(BASE_URL + href)
            elif href.startswith('http'):
                urls.append(href)

    # Alternative: try alphabetical pages A-Z
    # French alphabet starts with A
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        page_url = f"{BASE_URL}/?letter={letter}"
        html = fetch_page(page_url, session, delay=1.0)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/\d+-'))
            new_urls = []
            for link in links:
                href = link.get('href', '')
                if href.startswith('/') and not href == '/':
                    full_url = BASE_URL + href
                    if full_url not in urls:
                        new_urls.append(full_url)
                        urls.append(full_url)
            print(f"  Letter {letter}: {len(new_urls)} new URLs")
            time.sleep(1)

    return urls


def generate_urls_by_id(start: int = 1, end: int = 50000) -> list:
    """
    Generate URLs by incrementing ID.
    From the known URLs:
      17357 = faire_un_malheur
      23767 = le_malheur_des_uns...
      41172 = un_malheur_en_amène...
    The IDs are not sequential for entries, but we can probe them.
    """
    # We know the max is around 46210 entries, IDs go up to ~50000
    return [f"{BASE_URL}/{i}-" for i in range(start, end)]


# ============================================================
# MAIN
# ============================================================

def scrape_and_save(urls: list, conn: sqlite3.Connection,
                    session: requests.Session,
                    delay: float = 2.0):
    """Scrape URLs and save to database."""
    saved = 0
    skipped = 0
    failed = 0

    for i, url in enumerate(urls):
        # Check if already scraped
        existing = conn.execute(
            "SELECT id FROM fr_idiom_gak WHERE url=?", (url,)
        ).fetchone()
        if existing:
            skipped += 1
            continue

        html = fetch_page(url, session, delay=delay)
        if not html:
            failed += 1
            continue

        entry = parse_entry_page(html, url)

        if entry['fr_idiom']:
            conn.execute("""
                INSERT OR IGNORE INTO fr_idiom_gak
                (url, entry_num, fr_idiom, fr_variants, register,
                 ru_equivalents, fr_example, ru_example, raw_html)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry['url'], entry['entry_num'], entry['fr_idiom'],
                entry['fr_variants'], entry['register'],
                entry['ru_equivalents'], entry['fr_example'],
                entry['ru_example'], entry['raw_html']
            ))
            conn.commit()
            saved += 1

            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(urls)} — "
                      f"saved={saved} skipped={skipped} failed={failed}")
                print(f"  Last: {entry['fr_idiom'][:50]}")

        time.sleep(delay)

    return saved, skipped, failed


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Scrape 885.slovaronline.com')
    ap.add_argument('--test',   action='store_true', help='Test on known URLs')
    ap.add_argument('--index',  action='store_true', help='Fetch index to get all URLs')
    ap.add_argument('--scrape', action='store_true', help='Scrape all entries')
    ap.add_argument('--limit',  type=int, default=0, help='Limit number of entries')
    ap.add_argument('--delay',  type=float, default=2.0, help='Delay between requests (seconds)')
    ap.add_argument('--stats',  action='store_true', help='Show database stats')
    args = ap.parse_args()

    conn    = get_db()
    session = requests.Session()

    if args.stats:
        count = conn.execute("SELECT COUNT(*) FROM fr_idiom_gak").fetchone()[0]
        print(f"fr_idiom_gak table: {count} entries")
        sample = conn.execute(
            "SELECT fr_idiom, register, ru_equivalents FROM fr_idiom_gak LIMIT 5"
        ).fetchall()
        for row in sample:
            print(f"  {row['fr_idiom'][:50]:50s} [{row['register']}] → {row['ru_equivalents'][:50]}")

    elif args.test:
        print(f"Testing {len(TEST_URLS)} known URLs...")
        for url in TEST_URLS:
            print(f"\nFetching: {url}")
            html = fetch_page(url, session, delay=1.0)
            if html:
                entry = parse_entry_page(html, url)
                print(f"  Idiom:   {entry['fr_idiom']}")
                print(f"  Register:{entry['register']}")
                print(f"  Russian: {entry['ru_equivalents'][:80]}")
                print(f"  Example: {entry['fr_example'][:80]}")
            else:
                print(f"  FAILED — site may be blocking requests")
                print(f"  Try adding your browser cookies to HEADERS['Cookie']")
            time.sleep(args.delay)

    elif args.index:
        print("Fetching index to discover all entry URLs...")
        urls = get_index_urls(session)
        print(f"Found {len(urls)} URLs")
        # Save to file for later use
        url_file = PIPELINE_DIR / "885_urls.txt"
        with open(url_file, 'w') as f:
            f.write('\n'.join(urls))
        print(f"Saved to {url_file}")

    elif args.scrape:
        # Load URLs from file if available, otherwise use test URLs
        url_file = PIPELINE_DIR / "885_urls.txt"
        if url_file.exists():
            with open(url_file) as f:
                urls = [u.strip() for u in f if u.strip()]
        else:
            print("No URL file found — run --index first, or using test URLs")
            urls = TEST_URLS

        if args.limit:
            urls = urls[:args.limit]

        print(f"Scraping {len(urls)} URLs (delay={args.delay}s)...")
        saved, skipped, failed = scrape_and_save(urls, conn, session, args.delay)
        print(f"\nDone: saved={saved} skipped={skipped} failed={failed}")

    else:
        ap.print_help()
        print("\nQuick start:")
        print("  python pipeline/scrape_885.py --test")
        print("  python pipeline/scrape_885.py --index")
        print("  python pipeline/scrape_885.py --scrape --limit 100")

    conn.close()
# This line intentionally left blank

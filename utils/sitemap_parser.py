import gzip
import argparse
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def get_urls_from_sitemap(root_url, pattern="", max_depth=3, timeout=10) -> list:
    """
    Crawl a sitemap or sitemap index (supports .xml and .xml.gz), returning URLs
    whose text matches `pattern`. Recurses through nested indexes up to `max_depth`.
    """
    seen_sitemaps = set()
    found_urls = set()
    session = requests.Session()
    headers = {"User-Agent": "SitemapFetcher/1.0 (+https://example.com)"}

    def fetch_xml(url):
        print(f"Fetching sitemap: {url}")
        try:
            r = session.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            content = r.content
            # Handle gzip by header or extension
            if r.headers.get("Content-Type", "").lower() == "application/x-gzip" or url.lower().endswith(".gz"):
                content = gzip.decompress(content)
                print("Decompressed content:", content[:500])
            return BeautifulSoup(content, "xml")
        except Exception:
            print(f"Failed to fetch or parse sitemap: {url}")
            return None

    def walk(url, depth):
        if depth > max_depth or url in seen_sitemaps:
            return
        seen_sitemaps.add(url)

        soup = fetch_xml(url)
        if not soup:
            return

        # Detect sitemap index vs urlset
        if soup.find("sitemapindex"):
            # Recurse into each <sitemap><loc>
            for loc in soup.find_all("loc"):
                child = loc.get_text(strip=True)
                if not child:
                    continue
                # Resolve relative just in case (rare but harmless)
                child = urljoin(url, child)
                walk(child, depth + 1)

        elif soup.find("urlset"):
            # Collect <url><loc> entries
            for loc in soup.find_all("loc"):
                u = loc.get_text(strip=True)
                if not u:
                    continue
                if pattern in u:
                    found_urls.add(u)

        else:
            # Fallback: if the doc is a raw list of <loc>, treat like urlset
            locs = soup.find_all("loc")
            if locs:
                for loc in locs:
                    u = loc.get_text(strip=True)
                    if u and pattern in u:
                        found_urls.add(u)

    walk(root_url, depth=0)
    return sorted(found_urls)

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Fetch URLs from a sitemap.")
#     parser.add_argument("sitemap_url", help="URL of the sitemap or sitemap index")
#     parser.add_argument("--pattern", default="", help="Regex pattern to filter URLs")
#     parser.add_argument("--max_depth", type=int, default=3, help="Max recursion depth for sitemap indexes")
#     parser.add_argument("--timeout", type=int, default=10, help="HTTP request timeout in seconds")

#     args = parser.parse_args()
#     urls = get_urls_from_sitemap(args.sitemap_url, args.pattern, args.max_depth, args.timeout)
#     for url in urls:
#         print(url)
#     print(f"Found {len(urls)} URLs!")
import asyncio
import httpx
import re
import sys
import os
from concurrent.futures import ProcessPoolExecutor
import argparse
from urllib.parse import urlparse, urlunparse


# Define parameter URL regex pattern
PARAM_PATTERN = re.compile(r".*\?.*=.*")

WAYBACK_API = "https://web.archive.org/cdx/search/cdx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WaybackFetcher/1.0)"
}


async def fetch_all_urls(domain: str) -> list[str]:
    """Fetch all URLs from Wayback Machine for a specific domain with streaming."""
    params = {
        "url": f"*.{domain}/*",
        "collapse": "urlkey",
        "output": "text",
        "fl": "original"
    }

    lines = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=120) as client:
        async with client.stream("GET", WAYBACK_API, params=params) as response:
            response.raise_for_status()
            count = 0
            async for line in response.aiter_lines():
                if line:
                    lines.append(line)
                    count += 1
                    if count % 1000 == 0:
                        print(f"\r• Streamed {count} URLs for {domain}...", end="", flush=True)

    print(f"\n✅ Total URLs fetched for {domain}: {len(lines)}")
    return lines


def normalize_url(url: str) -> str:
    """Normalize URL to ensure consistent format."""
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Normalize scheme and netloc to lowercase
        netloc = parsed.netloc.lower()
        
        # Normalize path (remove double slashes)
        path = re.sub(r'/+', '/', parsed.path)
        
        # Normalize query parameters
        query = parsed.query
        
        # Reconstruct URL
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            path,
            parsed.params,
            query,
            parsed.fragment
        ))
        
        return normalized
    except:
        # If parsing fails, return original URL
        return url


def is_param_url(url: str) -> str | None:
    """Check if URL contains parameters."""
    normalized = normalize_url(url)
    return normalized if PARAM_PATTERN.search(normalized) else None


def filter_urls_parallel(urls: list[str]) -> list[str]:
    """Filter URLs using multiple CPU cores."""
    print("🔍 Filtering in parallel (multi-core)...")
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(is_param_url, urls))
    filtered = [url for url in results if url]
    print(f"✅ Filtered: {len(filtered)} parameter URLs")
    return filtered


async def save_to_file(filename: str, data: list[str]):
    def write_file():
        with open(filename, "w", encoding="utf-8") as f:
            f.write('\n'.join(data))
    await asyncio.to_thread(write_file)


async def process_domain(domain: str) -> tuple[list[str], list[str]]:
    """Process one domain and return results."""
    print(f"\n🌐 Processing domain: {domain}")
    
    print(f"🌐 Fetching URLs from Wayback Machine for {domain}...")
    all_urls = await fetch_all_urls(domain)

    print(f"🧹 Filtering URLs by parameters for {domain}...")
    filtered_urls = filter_urls_parallel(all_urls)
    
    return all_urls, filtered_urls


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Input file with domain list (one domain per line)")
    args = parser.parse_args()
    
    # Read domain list from file or input
    input_file = args.input or input("Enter the input file path with domain list: ").strip()
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            domains = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found.")
        return
    
    if not domains:
        print("❌ Error: No domains found in the input file.")
        return
    
    print(f"📋 Loaded {len(domains)} domains from {input_file}")
    
    # Initialize lists to collect all URLs
    all_urls = []
    all_param_urls = []
    
    # Process each domain
    for domain in domains:
        domain_all_urls, domain_param_urls = await process_domain(domain)
        
        # Add to global lists
        all_urls.extend(domain_all_urls)
        all_param_urls.extend(domain_param_urls)
        
        print(f"✅ Processed {domain}: {len(domain_all_urls)} URLs, {len(domain_param_urls)} parameter URLs")
    
    # Save all results to two files
    await asyncio.gather(
        save_to_file("all_urls.txt", all_urls),
        save_to_file("param_urls.txt", all_param_urls)
    )
    
    print(f"\n✅ Done! Results saved:")
    print(f"  • all_urls.txt ({len(all_urls)} URLs from all domains)")
    print(f"  • param_urls.txt ({len(all_param_urls)} parameter URLs from all domains)")


if __name__ == "__main__":
    asyncio.run(main())
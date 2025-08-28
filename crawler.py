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


async def fetch_all_urls(domain: str, output_queue: asyncio.Queue) -> list[str]:
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
                        # Send partial results to output queue
                        await output_queue.put(("partial", domain, count, 0))

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


async def append_to_file(filename: str, data: list[str]):
    """Append data to file instead of overwriting."""
    def write_file():
        with open(filename, "a", encoding="utf-8") as f:
            f.write('\n'.join(data) + '\n')
    await asyncio.to_thread(write_file)


async def process_domain(domain: str, output_queue: asyncio.Queue) -> tuple[int, int]:
    """Process one domain and save results immediately."""
    print(f"\n🌐 Processing domain: {domain}")
    
    print(f"🌐 Fetching URLs from Wayback Machine for {domain}...")
    all_urls = await fetch_all_urls(domain, output_queue)

    print(f"🧹 Filtering URLs by parameters for {domain}...")
    filtered_urls = filter_urls_parallel(all_urls)
    
    # Save results for this domain immediately
    await asyncio.gather(
        append_to_file("all_urls.txt", all_urls),
        append_to_file("param_urls.txt", filtered_urls)
    )
    
    print(f"✅ Processed {domain}: {len(all_urls)} URLs, {len(filtered_urls)} parameter URLs")
    
    # Send completion signal to output queue
    await output_queue.put(("complete", domain, len(all_urls), len(filtered_urls)))
    
    return len(all_urls), len(filtered_urls)


async def output_manager(output_queue: asyncio.Queue):
    """Manage real-time output and progress reporting."""
    total_all_urls = 0
    total_param_urls = 0
    processed_domains = 0
    
    while True:
        msg_type, domain, all_count, param_count = await output_queue.get()
        
        if msg_type == "partial":
            # Update progress during URL fetching
            print(f"\r• Progress: {total_all_urls + all_count} URLs fetched, {total_param_urls} parameter URLs", end="")
        elif msg_type == "complete":
            # Update final counts for completed domain
            total_all_urls += all_count
            total_param_urls += param_count
            processed_domains += 1
            
            print(f"\n✅ Domain {domain} completed:")
            print(f"   • {all_count} URLs found")
            print(f"   • {param_count} parameter URLs found")
            print(f"📊 Overall progress: {processed_domains} domains processed")
            print(f"   • Total URLs: {total_all_urls}")
            print(f"   • Total parameter URLs: {total_param_urls}")
            
            # Check if we're done (this would be set by main)
            if output_queue.qsize() == 0 and processed_domains == len(domains):
                break
        output_queue.task_done()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Input file with domain list (one domain per line)")
    args = parser.parse_args()
    
    # Clear output files at the beginning
    for filename in ["all_urls.txt", "param_urls.txt"]:
        if os.path.exists(filename):
            os.remove(filename)
    
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
    print(f"📝 Results will be saved to:")
    print(f"   • all_urls.txt (all URLs)")
    print(f"   • param_urls.txt (parameter URLs)")
    
    # Create output queue for real-time updates
    output_queue = asyncio.Queue()
    
    # Start output manager
    output_task = asyncio.create_task(output_manager(output_queue))
    
    # Process each domain concurrently
    tasks = []
    for domain in domains:
        task = asyncio.create_task(process_domain(domain, output_queue))
        tasks.append(task)
    
    # Wait for all domains to be processed
    await asyncio.gather(*tasks)
    
    # Signal completion to output manager
    await output_queue.put(("done", "", 0, 0))
    
    # Wait for output manager to finish
    await output_task
    
    print(f"\n✅ All domains processed!")
    print(f"📊 Final results:")
    print(f"   • all_urls.txt: {total_all_urls} URLs")
    print(f"   • param_urls.txt: {total_param_urls} parameter URLs")


if __name__ == "__main__":
    asyncio.run(main())

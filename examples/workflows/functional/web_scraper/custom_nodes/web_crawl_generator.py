import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from graphbook import step, param, output, source

@step("Custom/WebScrawlGenerator")
@source(is_generator=True)
@param("url", type="string", default="https://www.graphbook.ai/")
@param("max_depth", type="number", default=3)
@output("out")
def web_crawl_generator(ctx):
    """
    Crawl all links on a webpage with depth control.

    Args:
        url (str): Starting URL to crawl
        max_depth (int): Maximum depth to crawl using DFS
        
    Yields:
        out (str): URL of a page linked from the starting URL
    """
    base_url = ctx.url
    max_depth = ctx.max_depth
    
    # Prepare to crawl the web page
    visited_urls = set()
    all_links = set()
    
    def recursive_crawl(url, current_depth):
        # Stop if max depth reached or URL already visited
        if current_depth > max_depth or url in visited_urls:
            return
        
        try:
            # Prevent revisiting same URL
            visited_urls.add(url)
            
            # Fetch webpage content
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all <a> tags
            for link in soup.find_all('a', href=True):
                # Get absolute URL
                absolute_url = urljoin(url, link['href'])
                
                # Filter out external links if desired
                if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                    # Add to links set
                    all_links.add(absolute_url)
                    
                    # Recursively crawl if not visited
                    if absolute_url not in visited_urls:
                        recursive_crawl(absolute_url, current_depth + 1)
        
        except requests.RequestException as e:
            print(f"Error crawling {url}: {e}")
            
    recursive_crawl(base_url, 0)
    for link in all_links:
        yield {"out": link}

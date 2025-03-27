import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel
from firecrawl import FirecrawlApp

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool

def scrape_mission(url: str, firecrawl_app: FirecrawlApp) -> str:
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        firecrawl_app (FirecrawlApp): Instance of pre-authenticated FirecrawlApp.
    
    Returns:
        str: The mission statement scraped from the page.
    """
    scrape_results = firecrawl_app.scrape_url(url, {
        'formats': ['json'],
        'jsonOptions': {
            'schema': ExtractSchema.model_json_schema(),
        }
    })
    return scrape_results['json']['company_mission']

def scrape_title(url: str, firecrawl_app: FirecrawlApp) -> str:
    """
    Scrapes a web page for the title using Firecrawl.
    
    Args:
        url (str): The URL of the page to scrape.
        firecrawl_app (FirecrawlApp): Instance of pre-authenticated FirecrawlApp.
        
    Returns:
        str: The title scraped from the page.
    """
    scrape_results = firecrawl_app.scrape_url(url)
    return scrape_results['metadata']['og:title']
    

def crawl_links(base_url: str, api_key: str, max_depth=3) -> dict:
    """
    Crawl all links on a webpage with depth control.
    
    Args:
        base_url (str): Starting URL to crawl
        api_key (str): Firecrawl API key
        max_depth (int): Maximum depth of link traversal
    
    Returns:
        set: Unique links found during crawling
    """
    visited_urls = set()                            # Set to store unique visited URLs
    all_links = set()                               # Set to store all discovered links
    link_titles = {}                                # Dictionary to store link titles
    firecrawl_app = FirecrawlApp(api_key=api_key)   # Initialize Firecrawl app
    
    def recursive_crawl(url, current_depth):
        # Stop if max depth reached or URL already visited
        if current_depth > max_depth or url in visited_urls:
            return
        
        # Scrape title if not already done
        link_titles[url] = scrape_title(url, firecrawl_app)
        
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
    
    # Start crawling from base URL
    recursive_crawl(base_url, 0)
    
    return link_titles

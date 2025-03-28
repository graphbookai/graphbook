import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import graphbook as gb
from graphbook.core.steps import Step, SourceStep
from graphbook.core.resources import Resource
from pydantic import BaseModel
from firecrawl import FirecrawlApp

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool

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


class UrlSource(SourceStep):
    """Stores a web page URL for use in a workflow.

    Args:
        url (str): The URL of the page to use in a workflow.
    """
    RequiresInput = False
    Parameters = {
        "url": {
            "type": "string",
            "default": "https://www.graphbook.ai/"
        }
    }
    Outputs = ["url"]
    Category = "Custom"
    def __init__(self, url="https://www.graphbook.ai/"):
        super().__init__()
        self.url = url

    def load(self):
        return {"url": self.url}

    def route(self, data: dict) -> str:
        return "url"
    
class CrawlParams(Resource):
    """
    This resource is used to store the parameters for link traversal using depth-first search.
    
    Args:
        max_depth (int): The maximum depth of link traversal.
    """
    RequiresInput = False
    Parameters = {
        "max_depth": {
            "type": "number",
            "default": 3
        }
    }
    Outputs = ["max_depth"]
    Category = "Custom"
    def __init__(self, max_depth):
        super().__init__()
        self.max_depth = max_depth

    def value(self) -> int:
        return self.max_depth
    
class PersonalInfo(Resource):
    """
    This resource is used to store the personal information of the user. Currently,
    this only contains the API key for the Firecrawl API.
    
    Args:
        api_key (str): The API key for the Firecrawl API.
    """
    RequiresInput = False
    Parameters = {
        "api_key": {
            "type": "string",
            "default": "<API_KEY_HERE>"
        }
    }
    Outputs = ["api_key"]
    Category = "Custom"
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def value(self) -> str:
        return self.api_key


class ScrapeWebsite(Step):
    """
    Scrapes a website using Firecrawl and returns the titles of all its pages
    found using link traversal using depth-first search.

    Args:
        url (str): The base URL of the website to scrape.
        api_key (str): The Firecrawl API key.
        max_depth (int): The maximum depth of link traversal.
    """
    RequiresInput = True
    Parameters = {
        "api_key": {"type": "resource"},
        "max_depth": {"type": "resource"},
    }
    Outputs = ["page_titles"]
    Category = "Custom"
    def __init__(self, api_key: str, max_depth: int):
        super().__init__()
        self.page_titles = None
        self.api_key = api_key
        self.max_depth = max_depth

    def on_data(self, url: str):
        self.page_titles = crawl_links(url, self.api_key, self.max_depth)
        self.log(f"Scraped page titles: {self.page_titles}")

    def route(self, data: dict) -> str:
        return "page_titles"

g = gb.Graph()
@g()
def _():
    url_source = g.step(UrlSource)
    personal_info = g.resource(PersonalInfo)
    crawl_params = g.resource(CrawlParams)
    scrape_website = g.step(ScrapeWebsite)
    
    url_source.param("url", "https://www.graphbook.ai/")
    personal_info.param("api_key", "<API_KEY_HERE>")
    crawl_params.param("max_depth", 3)
    
    scrape_website.param("api_key", personal_info)
    scrape_website.param("max_depth", crawl_params)
    scrape_website.bind(url_source)

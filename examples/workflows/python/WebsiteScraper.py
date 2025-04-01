import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import graphbook as gb
from graphbook.core.steps import Step, GeneratorSourceStep
from graphbook.core.resources import Resource
from pydantic import BaseModel
from firecrawl import FirecrawlApp

class WebCrawlGenerator(GeneratorSourceStep):
    """
    Crawl all links on a webpage with depth control.

    Args:
        url (str): Starting URL to crawl
        max_depth (int): Maximum depth to crawl using DFS

    Yields:
        out (str): URL of a page linked from the starting URL
    """
    RequiresInput = False
    Parameters = {
        "url": {
            "type": "string",
            "default": "https://www.graphbook.ai/"
        },
        "max_depth": {
            "type": "number",
            "default": 3
        }
    }
    Outputs = ["out"]
    Category = "Custom"
    
    def __init__(self, url: str, max_depth: int):
        super().__init__()
        self.base_url = url
        self.max_depth = max_depth
        
        # Prepare to crawl the web page
        self.visited_urls = set()
        self.all_links = set()
        
    def recursive_crawl(self, url, current_depth):
        # Stop if max depth reached or URL already visited
        if current_depth > self.max_depth or url in self.visited_urls:
            return
        
        try:
            # Prevent revisiting same URL
            self.visited_urls.add(url)
            
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
                if urlparse(absolute_url).netloc == urlparse(self.base_url).netloc:
                    # Add to links set
                    self.all_links.add(absolute_url)
                    
                    # Recursively crawl if not visited
                    if absolute_url not in self.visited_urls:
                        self.recursive_crawl(absolute_url, current_depth + 1)
        
        except requests.RequestException as e:
            print(f"Error crawling {url}: {e}")
        
    def load(self):
        self.recursive_crawl(self.base_url, 0)
        for link in self.all_links:
            yield {"out": link}
    
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


class ScrapeTitle(Step):
    """
    Scrapes a web page for its title using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    RequiresInput = True
    Parameters = {
        "api_key": {"type": "resource"},
    }
    Outputs = ["out"]
    Category = "Custom"
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def on_data(self, url: str):
        # Firecrawl scrape
        app = FirecrawlApp(api_key=self.api_key)
        scrape_results = app.scrape_url(url)
        page_title = scrape_results['metadata']['og:title']
        
        self.log(f"Scraped page title: {page_title}")
        return page_title

g = gb.Graph()
@g()
def _():
    web_crawl_generator = g.step(WebCrawlGenerator)
    personal_info = g.resource(PersonalInfo)
    scrape_title = g.step(ScrapeTitle)
    
    web_crawl_generator.param("url", "https://www.graphbook.ai/")
    web_crawl_generator.param("max_depth", 3)
    personal_info.param("api_key", "<API_KEY_HERE>")
    
    scrape_title.param("api_key", personal_info)
    scrape_title.bind(web_crawl_generator, "out")

if __name__ == "__main__":
    # Run the workflow
    g.run()
    
    try:
        import time
        time.sleep(9999)
    except KeyboardInterrupt:
        pass

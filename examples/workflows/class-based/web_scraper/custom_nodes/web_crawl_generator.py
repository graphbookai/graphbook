import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from graphbook.core.steps import GeneratorSourceStep

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
        "base_url": {
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
    
    def __init__(self, base_url: str, max_depth: int):
        super().__init__()
        self.base_url = base_url
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
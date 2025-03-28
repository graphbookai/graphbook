from graphbook.core.steps import Step

from custom_nodes.firecrawl_utils import crawl_links

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
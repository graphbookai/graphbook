from firecrawl import FirecrawlApp
from graphbook.core.steps import Step

from custom_nodes.firecrawl_utils import scrape_mission

class ScrapePage(Step):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    RequiresInput = True
    Parameters = {
        "api_key": {"type": "resource"},
    }
    Outputs = ["mission_statement"]
    Category = "Custom"
    def __init__(self, api_key: str):
        super().__init__()
        self.mission_statement = None
        self.api_key = api_key

    def on_data(self, url: str):
        # Firecrawl scrape
        app = FirecrawlApp(api_key=self.api_key)
        self.mission_statement = scrape_mission(url, app)
        
        # self.mission_statement = f"Mission statement found from {url} using the key {self.api_key}"
        self.log(f"Scraped mission statement: {self.mission_statement}")

    def route(self, data: dict) -> str:
        return "mission_statement"
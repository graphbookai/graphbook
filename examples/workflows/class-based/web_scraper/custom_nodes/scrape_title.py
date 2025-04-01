from firecrawl import FirecrawlApp
from graphbook.core.steps import Step

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
    
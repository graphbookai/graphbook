from firecrawl import FirecrawlApp
from graphbook.core.steps import Step
from pydantic import BaseModel
from firecrawl import FirecrawlApp

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool

class ScrapeMission(Step):
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
    Outputs = ["out"]
    Category = "Custom"
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def on_data(self, url: str):
        # Firecrawl scrape
        app = FirecrawlApp(api_key=self.api_key)
        scrape_results = app.scrape_url(url, {
            'formats': ['json'],
            'jsonOptions': {
                'schema': ExtractSchema.model_json_schema(),
            }
        })
        mission_statement = scrape_results['json']['company_mission']
        
        self.log(f"Scraped mission statement: {mission_statement}")
        return mission_statement

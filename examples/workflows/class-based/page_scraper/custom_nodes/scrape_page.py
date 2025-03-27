from graphbook.core.steps import Step
from firecrawl import FirecrawlApp
from pydantic import BaseModel

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool

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
        self.url = None
        self.mission_statement = None
        self.api_key = api_key

    def on_data(self, data: dict):
        self.url = data['url']
        
        # Firecrawl scrape
        app = FirecrawlApp(api_key=self.api_key)
        scrape_results = app.scrape_url(self.url, {
            'formats': ['json'],
            'jsonOptions': {
                'schema': ExtractSchema.model_json_schema(),
            }
        })
        self.mission_statement = scrape_results['json']['company_mission']
        
        # self.mission_statement = f"Mission statement found from {self.url} using the key {self.api_key}"
        self.log(f"Scraped mission statement: {self.mission_statement}")

    def route(self, data: dict) -> str:
        return "mission_statement"
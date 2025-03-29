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
        return {"url": [self.url]}

    def route(self, data: dict) -> str:
        return "url"
    
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
        
        self.log(f"Mission statement found from {url} using the key {self.api_key}")
        self.log(f"Scraped mission statement: {self.mission_statement}")

    def route(self, data: dict) -> str:
        return "mission_statement"

g = gb.Graph()
@g()
def _():
    url_source = g.step(UrlSource)
    personal_info = g.resource(PersonalInfo)
    scrape_page = g.step(ScrapePage)
    
    url_source.param("url", "https://www.graphbook.ai/")
    personal_info.param("api_key", "fc-2f55841837434c39b7906be5be1c5fe0")
    
    scrape_page.param("api_key", personal_info)
    scrape_page.bind(url_source, "url")

if __name__ == "__main__":
    # Run the workflow
    g.run()
    
    try:
        import time
        time.sleep(9999)
    except KeyboardInterrupt:
        pass

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

g = gb.Graph()
@g()
def _():
    url_source = g.step(UrlSource)
    personal_info = g.resource(PersonalInfo)
    scrape_mission = g.step(ScrapeMission)
    
    url_source.param("url", "https://www.graphbook.ai/")
    personal_info.param("api_key", "<API_KEY_HERE>")
    
    scrape_mission.param("api_key", personal_info)
    scrape_mission.bind(url_source, "url")

if __name__ == "__main__":
    # Run the workflow
    g.run()
    
    try:
        import time
        time.sleep(9999)
    except KeyboardInterrupt:
        pass

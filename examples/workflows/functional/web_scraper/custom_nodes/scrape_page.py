from firecrawl import FirecrawlApp
from pydantic import BaseModel
from graphbook import step, param, output, event

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool

def route(data: dict, api_key: str) -> str:
    return "mission_statement"

@step("Custom/ScrapePage") # Category/Name
@param("api_key", type="resource")
@event("route", route)
@output("mission_statement")
def scrape_page(ctx, data: float):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    url = data['url']
    
    # Firecrawl scrape
    app = FirecrawlApp(api_key=ctx.api_key)
    scrape_results = app.scrape_url(url, {
        'formats': ['json'],
        'jsonOptions': {
            'schema': ExtractSchema.model_json_schema(),
        }
    })
    ctx.mission_statement = scrape_results['json']['company_mission']
    
    ctx.mission_statement = f"Mission statement found from {url} using the key {ctx.api_key}"
    ctx.log(f"Scraped mission statement: {ctx.mission_statement}")

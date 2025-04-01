from pydantic import BaseModel
from firecrawl import FirecrawlApp
from graphbook import step, param, output

# Define schema to extract contents into
class ExtractSchema(BaseModel):
    """JSON Schema for web scraping results."""
    company_mission: str
    supports_sso: bool
    is_open_source: bool
    is_in_yc: bool


@step("Custom/ScrapeMission") # Category/Name
@param("api_key", type="resource")
@output("out")
def scrape_mission(ctx, url: str):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    # Firecrawl scrape
    app = FirecrawlApp(api_key=ctx.api_key)
    scrape_results = app.scrape_url(url, {
        'formats': ['json'],
        'jsonOptions': {
            'schema': ExtractSchema.model_json_schema(),
        }
    })
    mission_statement = scrape_results['json']['company_mission']
    
    ctx.log(f"Scraped mission statement: {mission_statement}")
    return mission_statement

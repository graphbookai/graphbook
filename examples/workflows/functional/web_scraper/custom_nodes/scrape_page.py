from firecrawl import FirecrawlApp
from graphbook import step, param, output, event

from custom_nodes.firecrawl_utils import scrape_mission

def route(url: str, api_key: str) -> str:
    return "mission_statement"

@step("Custom/ScrapePage") # Category/Name
@param("api_key", type="resource")
@event("route", route)
@output("mission_statement")
def scrape_page(ctx, url: str):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    # Firecrawl scrape
    app = FirecrawlApp(api_key=ctx.api_key)
    ctx.mission_statement = scrape_mission(url, app)
    # ctx.mission_statement = f"Mission statement found from {url} using the key {ctx.api_key}"
    
    ctx.log(f"Scraped mission statement: {ctx.mission_statement}")

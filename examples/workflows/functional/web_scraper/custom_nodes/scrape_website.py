from graphbook import step, param, output, event

from custom_nodes.firecrawl_utils import crawl_links

def route(url: str, api_key: str) -> str:
    return "page_titles"

@step("Custom/ScrapeWebsite") # Category/Name
@param("api_key", type="resource")
@param("max_depth", type="resource")
@event("route", route)
@output("page_titles")
def scrape_page(ctx, url: str):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    ctx.page_titles = crawl_links(url, ctx.api_key, ctx.max_depth) # Firecrawl scrape
    # ctx.page_titles = f"Page titles found from {url} using the key {ctx.api_key} with max depth {ctx.max_depth}"
    
    ctx.log(f"Scraped page titles: {ctx.page_titles}")

from firecrawl import FirecrawlApp
from graphbook import step, param, output

@step("Custom/ScrapeTitle") # Category/Name
@param("api_key", type="resource")
@output("out")
def scrape_page(ctx, url: str):
    """
    Scrapes a web page for the mission statement using Firecrawl.

    Args:
        url (str): The URL of the page to scrape.
        api_key (str): The Firecrawl API key.
    """
    app = FirecrawlApp(api_key=ctx.api_key)
    scrape_results = app.scrape_url(url)
    page_title = scrape_results['metadata']['og:title']
    
    ctx.log(f"Scraped page title: {page_title}")
    return page_title

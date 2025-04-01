from graphbook import resource, param

@resource("Custom/PersonalInfo")
@param("api_key", type="string", default="<API_KEY_HERE>")
def url_source(ctx):
    """
    Store the personal information of the user. Currently,
    this only contains the API key for the Firecrawl API.

    Args:
        api_key (str): The API key for the Firecrawl API.
    """
    return ctx.api_key
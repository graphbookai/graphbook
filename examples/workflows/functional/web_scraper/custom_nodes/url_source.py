from graphbook import step, param, output, source

@step("Custom/UrlSource")
@source()
@param("url", type="string", default="https://www.graphbook.ai/")
@output("url")
def url_source(ctx):
    """
    Stores a web page URL for use in a workflow.

    Args:
        url (str): The URL of the page to use in a workflow.
    """
    yield {"url": ctx.url}
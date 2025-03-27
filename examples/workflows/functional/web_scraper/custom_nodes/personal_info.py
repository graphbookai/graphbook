from graphbook import Note
from graphbook import resource, param

@resource("Custom/PersonalInfo")
@param("api_key", type="string", default="fc-4004dda2dff3483f8207c71699b25e0b")
def url_source(ctx):
    """
    Stores a web page URL for use in a workflow.

    Args:
        url (str): The URL of the page to use in a workflow.
    """
    return ctx.api_key
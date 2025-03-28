from graphbook import resource, param

@resource("Custom/CrawlParams")
@param("max_depth", type="number", default=3)
def crawl_params(ctx):
    """
    Store the the parameters for link traversal using depth-first search.

    Args:
        max_depth (int): The maximum depth of link traversal.
    """
    return ctx.max_depth

import graphbook.steps as steps
import graphbook.resources as resources

class SimpleStep(steps.Step):
    RequiresInput = True
    Parameters = {}
    Outputs = ["out"]
    Category = "Simple"
    def __init__(self, id, logger):
        super().__init__(id, logger)

    def on_item(self, item, note):
        self.logger.log(item)

class SimpleResource(resources.Resource):
    Parameters = {}
    Category = "Simple"
    def __init__(self):
        super().__init__("Hello, World!")

import graphbook.steps as steps
import graphbook.resources as resources

class SimpleStep(steps.Step):
    RequiresInput = True
    Parameters = {}
    Outputs = ["out"]
    Category = "Simple"
    def __init__(self):
        super().__init__()

    def on_item(self, item, data):
        self.log(item)

class SimpleResource(resources.Resource):
    Parameters = {}
    Category = "Simple"
    def __init__(self):
        super().__init__("Hello, World!")

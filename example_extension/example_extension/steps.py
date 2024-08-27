import graphbook.steps as steps

class SimpleStep(steps.Step):
    RequiresInput = True
    Parameters = {}
    Outputs = ["out"]
    Category = "Simple"
    def __init__(self, id, logger):
        super().__init__(id, logger)

    def on_item(self, item, note):
        self.logger.log(item)

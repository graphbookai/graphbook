from transformers import AutoImageProcessor, AutoModel, ViTForImageClassification, ViTImageProcessor
from .base import Resource

class AutoImageProcessorResource(Resource):
    Category = "Huggingface/Transformers"
    Parameters = {
        "processor_name": {
            "type": "string",
            "description": "The name of the processor to load."
        }
    }
    def __init__(self, processor_name: str):
        self.processor = AutoImageProcessor.from_pretrained(processor_name)
        super().__init__(self.processor)

    def value(self):
        return self.processor
    
class AutoModelResource(Resource):
    Category = "Huggingface/Transformers"
    Parameters = {
        "model_name": {
            "type": "string",
            "description": "The name of the model to load."
        }
    }
    def __init__(self, model_name: str):
        self.model = AutoModel.from_pretrained(model_name)
        super().__init__(self.model)

    def value(self):
        return self.model

class ViTForImageClassificationResource(Resource):
    Category = "Huggingface/Transformers"
    Parameters = {
        "model_name": {
            "type": "string",
            "description": "The name of the model to load."
        }
    }
    def __init__(self, model_name: str):
        self.model = ViTForImageClassification.from_pretrained(model_name)
        super().__init__(self.model)

    def value(self):
        return self.model

class ViTImageProcessorResource(Resource):
    Category = "Huggingface/Transformers"
    Parameters = {
        "model_name": {
            "type": "string",
            "description": "The name of the model to load."
        }
    }
    def __init__(self, model_name: str):
        self.model = ViTImageProcessor.from_pretrained(model_name)
        super().__init__(self.model)

    def value(self):
        return self.model

from graphbook import resource, param, step
from transformers import ViTForImageClassification, ViTImageProcessor


@resource("Huggingface/ViTForImageClassification")
@param(
    "model_name",
    type="string",
    description="The name of the model to load.",
    default="imjeffhi/pokemon_classifier",
)
def vit_for_image_classification(ctx):
    """
    A resource that loads a Vision Transformer model for image classification.

    Args:
        model_name (str): The name of the model to load taken from Huggingface's model hub.
    """
    return ViTForImageClassification.from_pretrained(ctx.model_name).to("cuda")


@resource("Huggingface/ViTImageProcessor")
@param(
    "image_processor",
    type="string",
    description="The name of the image processor.",
    default="imjeffhi/pokemon_classifier",
)
def vit_image_processor(ctx):
    """
    A resource that loads the corresponding image processor.

    Args:
        image_processor (str): The name of the image processor taken from Huggingface's model hub. This is typically the same as the model name.
    """
    return ViTImageProcessor.from_pretrained(ctx.image_processor)

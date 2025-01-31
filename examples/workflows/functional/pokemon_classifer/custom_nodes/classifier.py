from graphbook import Note, step, batch, param, event
import torch
import torchvision.transforms.functional as F
from PIL import Image
from typing import List


@staticmethod
def load_fn(item: dict) -> torch.Tensor:
    im = Image.open(item["value"])
    image = F.to_tensor(im)
    if image.shape[0] == 1:
        image = image.repeat(3, 1, 1)
    elif image.shape[0] == 4:
        image = image[:3]
    return image

def init_classifier(ctx, **kwargs):
    ctx.tp = 0
    ctx.num_samples = 0


@step("Custom/PokemonClassifier")
@batch(8, "image", load_fn=load_fn)
@event("__init__", init_classifier)
@param("model", type="resource")
@param("image_processor", type="resource")
@torch.no_grad()
def pokemon_classifier(
    ctx, tensors: List[torch.Tensor], items: List[dict], notes: List[Note]
):
    """
    The PokemonClassifier step uses the input Vision Transformer model and image processor to classify incoming images of Pokemon.

    Args:
        tensors (List[torch.Tensor]): A list of tensors containing the images to classify.
        items (List[dict]): A list of dictionaries containing the items to classify.
        notes (List[Note]): A list of notes containing the notes to classify.
    """
    extracted = ctx.image_processor(
        images=tensors, do_rescale=False, return_tensors="pt"
    )
    extracted = extracted.to("cuda")
    predicted_id = ctx.model(**extracted).logits.argmax(-1)
    for t, item, note in zip(predicted_id, items, notes):
        item["prediction"] = ctx.model.config.id2label[t.item()]
        ctx.log(f"Predicted {item['value']} as {item['prediction']}")
        if item["prediction"] == note["name"]:
            ctx.tp += 1
        ctx.num_samples += 1
    if ctx.num_samples > 0:
        ctx.log(f"Accuracy: {ctx.tp/ctx.num_samples:.2f}")

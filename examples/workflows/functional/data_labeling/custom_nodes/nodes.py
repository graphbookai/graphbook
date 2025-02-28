from graphbook import step, prompt
from graphbook.prompts import selection_prompt, bool_prompt
import random


def dog_or_cat(ctx, data):
    return selection_prompt(data, choices=["dog", "cat"], show_images=True)


@step("Prompts/Label")
@prompt(dog_or_cat)
def label_images(ctx, data, response: str):
    data["label"] = response


def corrective_prompt(ctx, data):
    if data["prediction_confidence"] < 0.65:
        return bool_prompt(
            data,
            msg=f"Model prediction ({data['pred']}) was uncertain. Is its prediction correct?",
            show_images=True,
        )
    else:
        return None


@step("Prompts/CorrectModelLabel")
@prompt(corrective_prompt)
def correct_model_labels(ctx, data, response: bool):
    if response:
        ctx.log("Model is correct!")
        data["label"] = data["pred"]
    else:
        ctx.log("Model is incorrect!")
        if data["pred"] == "dog":
            data["label"] = "cat"
        else:
            data["label"] = "dog"


@step("Prompts/Model")
def model_prediction(ctx, data):
    sample = random.random()
    conf = sample
    if sample < 0.5:
        data["pred"] = "cat"
        conf = 1 - sample
    else:
        data["pred"] = "dog"
    data["prediction_confidence"] = conf

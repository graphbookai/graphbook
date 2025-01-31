from graphbook import Note, prompt, selection_prompt, bool_prompt, step
import random


def dog_or_cat(ctx, note: Note):
    return selection_prompt(note, choices=["dog", "cat"], show_images=True)


@step("Prompts/Label")
@prompt(dog_or_cat)
def label_images(ctx, note: Note, response: str):
    note["label"] = response


def corrective_prompt(ctx, note: Note):
    if note["prediction_confidence"] < 0.65:
        return bool_prompt(
            note,
            msg=f"Model prediction ({note['pred']}) was uncertain. Is its prediction correct?",
            show_images=True,
        )
    else:
        return None


@step("Prompts/CorrectModelLabel")
@prompt(corrective_prompt)
def correct_model_labels(ctx, note: Note, response: bool):
    if response:
        ctx.log("Model is correct!")
        note["label"] = note["pred"]
    else:
        ctx.log("Model is incorrect!")
        if note["pred"] == "dog":
            note["label"] = "cat"
        else:
            note["label"] = "dog"


@step("Prompts/Model")
def model_prediction(ctx, note: Note):
    sample = random.random()
    conf = sample
    if sample < 0.5:
        note["pred"] = "cat"
        conf = 1 - sample
    else:
        note["pred"] = "dog"
    note["prediction_confidence"] = conf

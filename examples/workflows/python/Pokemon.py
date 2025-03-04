import graphbook as gb
from custom_nodes.pokemon_nodes import PokemonClassifier, ViTForImageClassificationResource, LoadImageDataset, ViTImageProcessorResource

g = gb.Graph()

@g()
def _():
    g.md(
"""# Pokemon Classification

This workflow classifies incoming Pokemon images

## Overview

This workflow uses a *convolutional neural network (CNN)* to classify incoming Pokemon images. The CNN is trained on a large dataset of Pokemon images and can accurately identify the species of the Pokemon in the input image. The workflow takes an image as input and outputs the predicted Pokemon species along with a confidence score. It can be used in various applications such as Pokemon games, image recognition systems, and Pokemon-related research projects.
""")
    
    # Create nodes
    step_0 = g.step(LoadImageDataset)
    step_1 = g.step(PokemonClassifier)
    resource_2 = g.resource(gb.resources.FunctionResource)
    step_3 = g.step(gb.steps.Split)
    resource_4 = g.resource(ViTForImageClassificationResource)
    resource_5 = g.resource(ViTImageProcessorResource)

    # Setup parameters
    step_0.param('image_dir', "/media/sam/shared/alternative/pokemon")
    step_1.param('batch_size', 8)
    step_1.param('item_key', "image")
    step_1.param('model', resource_4)
    step_1.param('image_processor', resource_5)
    resource_2.param('val', """def my_favorite_pokemon(note: Note) -> bool:
        return note["name"] in ["Pikachu", "Charmander", "Bulbasaur"]""")
    step_3.param('split_fn', resource_2)
    resource_4.param('model_name', "imjeffhi/pokemon_classifier")
    resource_5.param('image_processor', "imjeffhi/pokemon_classifier")

    # Bind steps
    step_1.bind(step_3, 'A')
    step_3.bind(step_0, 'out')

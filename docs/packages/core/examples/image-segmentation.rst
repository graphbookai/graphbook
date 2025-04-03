.. meta::
    :description: Learn how to remove the background from images using a pre-trained model in Graphbook.
    :twitter:description: Learn how to remove the background from images using a pre-trained model in Graphbook.

Image Segmentation
##################

.. _transformers: https://huggingface.co/docs/transformers

.. note::
    Requires Huggingface transformers_

In this guide, we will use a pre-trained model, RMBG-1.4, from Bria AI downloadable from Huggingface to remove the background from images.
We can use the same dataset from the Pokemon Image Classification guide, so let's reuse the LoadImageDataset source step.

Create the Model Resource
=========================

First, let's create a new Resource class that will store the RMBG-1.4 model:

.. code-block:: python

    from graphbook.resources import Resource
    from transformers import AutoModelForImageSegmentation

    class RMBGModel(Resource):
        Category = "Custom"
        Parameters = {
            "model_name": {
                "type": "string",
                "description": "The name of the image processor.",
                "default": "briai/RMBG-1.4",
            }
        }

        def __init__(self, model_name: str):
            super().__init__(
                AutoModelForImageSegmentation.from_pretrained(
                    model_name, trust_remote_code=True
                ).to("cuda")
            )

Create the BatchStep
====================

Then, create a new BatchStep class that uses the RMBG-1.4 model to remove the background from the images:

.. code-block:: python

    from graphbook.steps import BatchStep, SourceStep
        import torchvision.transforms.functional as F
    import torch.nn.functional
    import torch
    from typing import List
    from PIL import Image
    import os
    import os.path as osp

    class RemoveBackground(BatchStep):
        RequiresInput = True
        Parameters = {
            "model": {
                "type": "resource",
            },
            "batch_size": {
                "type": "number",
                "default": 8,
            },
            "item_key": {
                "type": "string",
                "default": "image",
            },
            "output_dir": {
                "type": "string",
            },
        }
        Outputs = ["out"]
        Category = "Custom"

        def __init__(
            self,
            id,
            logger,
            batch_size,
            item_key,
            output_dir,
            model: AutoModelForImageSegmentation,
        ):
            super().__init__(batch_size, item_key)
            self.model = model
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

        @staticmethod
        def load_fn(item: dict) -> torch.Tensor:
            im = Image.open(item["value"])
            image = F.to_tensor(im)
            if image.shape[0] == 1:
                image = image.repeat(3, 1, 1)
            elif image.shape[0] == 4:
                image = image[:3]

            return image

        @staticmethod
        def dump_fn(data: Tuple[torch.Tensor, str]):
            t, output_path = data
            dir = osp.dirname(output_path)
            os.makedirs(dir, exist_ok=True)
            img = F.to_pil_image(t)
            img.save(output_path)

        def get_output_path(self, data, input_path):
            return osp.join(self.output_dir, data["name"], osp.basename(input_path))

        @torch.no_grad()
        def on_item_batch(
            self, tensors: List[torch.Tensor], items: List[dict], data: List[dict]
        ):
            og_sizes = [t.shape[1:] for t in tensors]

            images = [
                F.normalize(
                    torch.nn.functional.interpolate(
                        torch.unsqueeze(image, 0), size=[1024, 1024], mode="bilinear"
                    ),
                    [0.5, 0.5, 0.5],
                    [1.0, 1.0, 1.0],
                )
                for image in tensors
            ]
            images = torch.stack(images).to("cuda")
            images = torch.squeeze(images, 1)
            tup = self.model(images)
            result = tup[0][0]
            ma = torch.max(result)
            mi = torch.min(result)
            result = (result - mi) / (ma - mi)
            resized = [
                torch.squeeze(
                    torch.nn.functional.interpolate(
                        torch.unsqueeze(image, 0), size=og_size, mode="bilinear"
                    ),
                    0,
                ).cpu()
                for image, og_size in zip(result, og_sizes)
            ]
            paths = [
                self.get_output_path(d, input["value"])
                for input, d in zip(items, data)
            ]
            removed_bg = list(zip(resized, paths))
            for path, d in zip(paths, data):
                masks = d["masks"]
                if masks is None:
                    masks = []
                masks.append({"value": path, "type": "image"})
                d["masks"] = masks

            return removed_bg

This node will generate masks of the foreground using the RMBG-1.4 model and output the resulting mask as images by saving them to disk.
See that there is one notable difference in RemoveBackground compared to PokemonClassifier.
In addition to loading data from disk, it is now dumping data to the disk, the model outputs. 
It is important that we offload this work, too, to background processes to have an efficient data pipeline.
To do this, we return a dictionary of tensors in the ``on_item_batch`` method which tells Graphbook to send the resulting items to the worker processes to be saved.
Each element inside ``removed_bg`` is sent to the ``dump_fn`` method which executes our saving under one of the worker processes.
The ``dump_fn`` method is our custom function used to save the resulting image masks to disk.

Lastly, connect your nodes like so:

.. image:: /_static/6_segm_workflow.png
    :alt: Remove Background Workflow
    :align: center

Make sure to specify the output directory in the RemoveBackground node, and where your image dataset is inside the LoadImageDataset node.
Note that we use another built-in node called DumpJSONL that saves the resulting output dict as serialized JSON lines to a file.
This is useful for us to check on our outputs later on.

If you remember that game "Who's that Pokemon?" from the Pokemon TV show, you can now play it with your friends using these generated masks!

.. note::

    More guides are coming soon!

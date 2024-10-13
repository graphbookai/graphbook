.. meta::
    :description: Learn how to write data with Graphbook's custom muiltiprocessing capabilities ensuring that your GPU is efficiently utilized.
    :twitter:description: Learn how to write data with Graphbook's custom muiltiprocessing capabilities ensuring that your GPU is efficiently utilized.

Dump Data
#########


You can also use the worker pool to parallelize the dumping of data to disk/network with your own custom defined function.

.. seealso::

    :ref:`Workers` - Learn more about the workers behind your pipeline.

To parallelize dumping, we still need to use the decorator :func:`graphbook.batch` because dumping is made available to :class:`graphbook.steps.BatchStep`.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/batch_steps.py

            from graphbook import Note, step, batch
            from PIL import Image
            from typing import List
            import torch
            import torchvision.transforms.functional as F

            # Custom defined function that will execute in parallel
            @staticmethod
            def save_image(image: Image.Image, output_path: str):
                image.save(output_path)

            @step("LoadImages")
            @batch(8, "image_paths", dump_fn=save_image, load_fn=convert_to_tensor)
            @staticmethod
            def on_load_images(tensors: List[torch.Tensor], items: List[dict], notes: List[Note]):
                # Generate images
                ...

                args = []
                for image, item in zip(images, items):
                    input_path = items['value']
                    output_path = input_path.replace('.jpg', '_processed.jpg')
                    args.append((image, output_path))
                return args
    
    .. tab-item:: class

        .. code-block:: python

            from graphbook.steps import BatchStep
            from graphbook import Note
            from PIL import Image
            from typing import List
            import torch
            import torchvision.transforms.functional as F

            class LoadImages(BatchStep):
                RequiresInput = True
                Parameters = {
                    "batch_size": {"type": "number", "default": 8},
                    "item_key": {"type": "string", "default": "image_paths"}
                }
                Outputs = ["out"]
                Category = ""

                def __init__(self, batch_size, item_key):
                    super().__init__(batch_size, item_key)

                # Custom defined function that will execute in parallel
                @staticmethod
                def dump_fn(image: Image.Image, output_path: str):
                    image.save(output_path)

                @staticmethod
                def on_item_batch(tensors: List[torch.Tensor], items: List[dict], notes: List[Note]):
                    # Generate images
                    ...

                    args = []
                    for image, item in zip(images, items):
                        input_path = items['value']
                        output_path = input_path.replace('.jpg', '_processed.jpg')
                        args.append((image, output_path))
                    return args

Here, we override the :meth:`graphbook.steps.BatchStep.dump_fn` method to define our custom function to dump images to disk in parallel with the main process.
The event :meth:`graphbook.steps.BatchStep.on_item_batch` can return a list of parameters to pass to ``dump_fn(**args)`` for each element in the return output.

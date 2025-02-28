.. meta::
    :description: Learn how to batch data with Graphbook's custom muiltiprocessing capabilities ensuring that your GPU is efficiently utilized.
    :twitter:description: Learn how to batch data with Graphbook's custom muiltiprocessing capabilities ensuring that your GPU is efficiently utilized.

Batch Data
##########

One of the most important features offered by Graphbook is its multiprocessing capabilities.
Graphbook has a worker pool that can be used to parallelize the loading of data with your own custom defined function.
You can also use it to parallelize the writing of outputs, but that is covered in the next section.

.. seealso::

    :ref:`Workers` - Learn more about the workers behind your pipeline.

Load and Batch Data
===================

In this section, we will cover the decorator :func:`graphbook.batch`, and how to use it to parallelize the loading of data.
For example, to create a batch step that loads images from the file system and convert them to PyTorch Tensors, you can use the following code:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/batch_steps.py

            from graphbook import step, batch
            from PIL import Image
            from typing import List
            import torch
            import torchvision.transforms.functional as F

            # Custom defined function that will execute in parallel
            @staticmethod
            def convert_to_tensor(item: dict) -> torch.Tensor:
                image_path = item["value"]
                pil_image = Image.open(image_path)
                return F.to_tensor(pil_image)

            @step("LoadImages")
            @batch(8, "image_paths", load_fn=convert_to_tensor)
            @staticmethod
            def on_load_images(tensors: List[torch.Tensor], items: List[dict], data: List[dict]):
                for tensor, d in zip(tensors, data):
                    if d["tensor"] is None:
                        d["tensor"] = []
                    d["tensor"].append(tensor)
    
    .. tab-item:: class

        .. code-block:: python

            from graphbook.steps import BatchStep
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
                def load_fn(item: dict) -> torch.Tensor:
                    image_path = item["value"]
                    pil_image = Image.open(image_path)
                    return F.to_tensor(pil_image)

                @staticmethod
                def on_item_batch(tensors: List[torch.Tensor], items: List[dict], data: List[dict]):
                    for tensor, d in zip(tensors, data):
                        if d["tensor"] is None:
                            d["tensor"] = []
                        d["tensor"].append(tensor)

The above step simply loads images from the file system and converts them to PyTorch Tensors assuming that the dictionaries containing the image paths come from another :ref:`source step<Load Images>`.

Here is a breakdown of what we did:

#. First, we defined a custom function ``convert_to_tensor`` that will execute in parallel. This function takes the input item that is specified by our batch step.
#. We give a name to our step "LoadImages".
#. We use the :func:`graphbook.batch` decorator to specify that this step is a batch step. The first parameter is the default batch size, the second parameter is the item key from the expected dict that we will use, and the third parameter is the function that we defined in the first step.

    .. note::

        The first two parameters ``batch_size`` and ``item_key`` will be configurable in the UI.
        If you are designing the step as a class, you must manually define these parameters.

#. We mark the decorated method as static, because we do not care about the underlying class instance.
#. We define the :meth:`graphbook.steps.BatchStep.on_item_batch` method that will be executed which simply assigns the output tensors to the dict that they came from.

.. tip::

    A batch step decorates :meth:`graphbook.steps.BatchStep.on_item_batch` by default.
    This method is executed with the following parameters, respectively:

    * The tensors (or whatever we output from out defined function)
    * The associated input item
    * The associated dict that it came from

    All three lists should be of size equal to the batch size.

Passing Data to an ML Model
===========================

Of course, if you're batching inputs such as tensors, you are most likely preparing them to be loaded into the GPU to pass them into an ML model.
By immediately passing your tensors to the model, we can avoid the large memory overhead of storing the tensors in the dicts.
You can do so with the following example:


.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/batch_steps.py

            from graphbook import step, batch
            from typing import List
            import torch

            @step("MyMLModel")
            @batch(8, "image_paths", load_fn=convert_to_tensor)
            @param("model", type="resource")
            @torch.no_grad()
            def on_load_images(ctx, images: List[torch.Tensor], items: List[dict], data: List[dict]):
                batch = torch.stack(images).to("cuda")
                outputs = ctx.model(batch)

                # (Option 1) Store the model's outputs in the items
                for output, item in zip(images, items):
                    item["output"] = output

                # (Option 2) Store the model's outputs in the dict
                for output, d in zip(outputs, data):
                    if d["output"] is None:
                        d["output"] = []
                    d["output"].append(output)

    .. tab-item:: class

        .. code-block:: python

            from graphbook.steps import BatchStep
                        from typing import List
            import torch

            class MyMLModel(BatchStep):
                RequiresInput = True
                Parameters = {
                    "batch_size": {"type": "number", "default": 8},
                    "item_key": {"type": "string", "default": "image_paths"},
                    "model": {"type": "resource"}
                }
                Outputs = ["out"]
                Category = ""

                def __init__(self, batch_size, item_key, model):
                    super().__init__(batch_size, item_key)
                    self.model = model
                
                ...

                @torch.no_grad()
                def on_item_batch(self, images: List[torch.Tensor], items: List[dict], data: List[dict]):
                    batch = torch.stack(images).to("cuda")
                    outputs = self.model(batch)

                    # (Option 1) Store the model's outputs in the items
                    for output, item in zip(images, items):
                        item["output"] = output

                    # (Option 2) Store the model's outputs in the dict
                    for output, d in zip(outputs, data):
                        if d["output"] is None:
                            d["output"] = []
                        d["output"].append(output)

The example above assumes that there is already a resource containing a model, loaded into the GPU, that can be used to process the images.


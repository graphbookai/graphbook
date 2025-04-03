.. meta::
    :description: Learn how to load a source of images into your data processing pipelines.
    :twitter:description: Learn how to load a source of images into your data processing pipelines.

.. _Load Images:

Load Images
###########

Graphbook will attempt to look for images inside of output data in an workflow and automatically render those images in the web UI.
In this guide, we will properly load a source of images into our data processing pipelines, so that Graphbook can render them.
Essentially, this is made possible with the help of the :func:`graphbook.utils.image` function.

Load by File Paths
==================

.. tip::

    :func:`graphbook.utils.image` is a helper function that converts an image file or a PIL Image into a format that allows Graphbook to detect and render them in the web UI.
    Internally, it just outputs a dict with the value, ``{"type": "image", "value": "<input>"}``.

.. tab-set::
    
    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook import step, source, param, utils

            @step("ImageSource")
            @source()
            @param("img_path", "string", default="path/to/images")
            def image_source(ctx: Step):
                for root, dirs, files in os.walk(ctx.img_path):
                    for file in files:
                        yield {
                            "out": {
                                "img": utils.image(os.path.join(root, file))
                            }
                        }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook.steps import GeneratorSourceStep
            from graphbook import utils

            class ImageSource(GeneratorSourceStep):
                RequiresInput = False
                Parameters = {"img_path": {"type": "string", "default": "path/to/images"}}
                Outputs = ["out"]
                Category = ""

                def __init__(self, img_path):
                    super().__init__()
                    self.img_path = img_path

                def load(self):
                    for root, dirs, files in os.walk(self.img_path):
                        for file in files:
                            yield {
                                "out": {
                                    "img": utils.image(os.path.join(root, file))
                                }
                            }

Load by PIL Images
==================

If you have a PIL Image object, you can similarly use :func:`graphbook.utils.image`.

.. code-block:: python
    :caption: Example with PIL Image

        from PIL import Image
        ...
        yield {
            "out": {
                "img": utils.image(Image.open(os.path.join(root, file)))
            }
        }

Load without Generators
=======================

Alternatively, if you don't want to use generators (with the ``yield`` keyword), you can use ``@source(False)`` or :class:`graphbook.steps.SourceStep` to return all of the data at once.
This is not recommended for large datasets because it will load all of the data in one step causing a bottleneck in your workflow.

.. tab-set::
    
    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook import step, source, param, utils

            @step("ImageSource")
            @source(False)
            @param("img_path", "string", default="path/to/images")
            def image_source(ctx: Step):
                images = { "out": [] }
                for root, dirs, files in os.walk(ctx.img_path):
                    for file in files:
                        images["out"].append({
                            "img": utils.image(os.path.join(root, file))
                        })
                return images

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook.steps import SourceStep
            from graphbook import utils

            class ImageSource(SourceStep):
                RequiresInput = False
                Parameters = {"img_path": {"type": "string", "default": "path/to/images"}}
                Outputs = ["out"]
                Category = ""

                def __init__(self, img_path):
                    super().__init__()
                    self.img_path = img_path

                def load(self):
                    images = { "out": [] }
                    for root, dirs, files in os.walk(self.img_path):
                        for file in files:
                            images["out"].append({
                                "img": utils.image(os.path.join(root, file))
                            })
                    return images

Arrays of Images
================

If you an have an item containing an array of images, Graphbook can also render them.

.. code-block:: python
    :caption: Working Example

        # OK
        ...
        yield {
            "out": {
                "images": [utils.image(os.path.join(root, file)) for file in files]
            }
        }

However, if your images are nested in a dictionary or under any other structure, it will not render them.

.. code-block:: python
    :caption: Not a Working Example

        # Not OK
        ...
        yield {
            "out": {
                "images": {file: utils.image(os.path.join(root, file)) for file in files}
            }
        }

.. meta::
    :description: Learn how to load a source of images into your data processing pipelines.
    :twitter:description: Learn how to load a source of images into your data processing pipelines.

Load Images
###########

Graphbook will attempt to look for images inside of output notes in an workflow and automatically render those images in the web UI.
In this guide, we will properly load a source of images into our data processing pipelines, so that Graphbook can render them.
Essentially, this is made possible with the help of the :func:`graphbook.utils.image` function.

.. tip::

    :func:`graphbook.utils.image` is a helper function that converts an image file or a PIL Image into a format that allows Graphbook to detect and render them in the web UI.
    Internally, it just outputs a dict with the value, ``{"type": "image", "value": "<input>"}``.

.. tab-set::
    
    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook import Note, step, source, param, utils

            @step("ImageSource")
            @source()
            @param("img_path", "string", default="path/to/images")
            def image_source(ctx: Step):
                for root, dirs, files in os.walk(ctx.img_path):
                    for file in files:
                        yield Note({
                            "img": utils.image(os.path.join(root, file))
                        })

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook.steps import GeneratorSourceStep
            from graphbook import Note, utils

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
                            yield Note({
                                "img": utils.image(os.path.join(root, file))
                            })

Alternatively, if you don't want to use generators (with the ``yield`` keyword), you can use ``@source(False)`` or :class:`graphbook.steps.SourceStep` to return all of the notes at once.
This is not recommended for large datasets because it will load all of the data in one step causing a bottleneck in your workflow.

.. tab-set::
    
    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook import Note, step, source, param, utils

            @step("ImageSource")
            @source(False)
            @param("img_path", "string", default="path/to/images")
            def image_source(ctx: Step):
                notes = { "out": [] }
                for root, dirs, files in os.walk(ctx.img_path):
                    for file in files:
                        note = Note({
                            "img": utils.image(os.path.join(root, file))
                        })
                        notes["out"].append(note)
                return notes

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/image_source.py

            import os.path
            from graphbook.steps import SourceStep
            from graphbook import Note, utils

            class ImageSource(SourceStep):
                RequiresInput = False
                Parameters = {"img_path": {"type": "string", "default": "path/to/images"}}
                Outputs = ["out"]
                Category = ""

                def __init__(self, img_path):
                    super().__init__()
                    self.img_path = img_path

                def load(self):
                    notes = { "out": [] }
                    for root, dirs, files in os.walk(self.img_path):
                        for file in files:
                            note = Note({
                                "img": utils.image(os.path.join(root, file))
                            })
                            notes["out"].append(note)
                    return notes

Arrays of Images
================

If you an have an item containing an array of images, Graphbook can also render them.

.. code-block:: python
    :caption: Working Example

        # OK
        ...
        yield Note({
            "images": [utils.image(os.path.join(root, file)) for file in files] 
        })

However, if your images are nested in a dictionary or under any other structure, it will not render them.

.. code-block:: python
    :caption: Not a Working Example

        # Not OK
        ...
        yield Note({
            "images": {file: utils.image(os.path.join(root, file)) for file in files}
        })

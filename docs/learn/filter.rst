.. meta::
    :description: How to filter data with Graphbook. Learn how we can filter notes and handle notes differently as they traverse different branches.
    :twitter:description: How to filter data with Graphbook. Learn how we can filter notes and handle notes differently as they traverse different branches.

.. _Filter:

Filter
######

Filtering data based on certain conditions and criteria is a common operation in data processing pipelines.
Graphbook provides a way to filter notes and handle notes differently as they traverse different branches.
Every step can have multiple output slots, and each slot can be used to route notes to different parts of the graph.
You can route a note to a specific output with the :meth:`graphbook.steps.Step.forward_note` method or event.

Filter Notes
============

.. tip::

    The default output slot is "out". To create other output slots, use the :func:`graphbook.output` decorator.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output, Note

            @step("Filter", event="forward_note")
            @param("threshold", type="number", default=0.5)
            @output("good", "junk")
            def filter(ctx, note: Note):
                if note['value'] > ctx.threshold:
                    return { "good": [note] }
                return { "junk": [note] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            from graphbook import Note

            class Filter(Step):
                RequiresInput = True
                Parameters = {
                    "threshold": {
                        "type": "number",
                        "default": 0.5
                    }
                }
                Outputs = ["good", "junk"]
                Category = ""
                def __init__(self, threshold):
                    super().__init__()
                    self.threshold = threshold

                def forward_note(self, note: Note) -> str:
                    if note['value'] > ctx.threshold:
                        return { "good": [note] }
                    return { "junk": [note] }

Or otherwise, you can return just the output slot name as a short-hand way of routing the note.


.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def filter(ctx, note: Note):
                if note['value'] > ctx.threshold:
                    return "good"
                return "junk"
    
    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def forward_note(self, note: Note) -> str:
                if note['value'] > self.threshold:
                    return "good"
                return "junk"

Filter Based on a Given Function
================================

You can also filter notes based on a given function with the resource :class:`graphbook.resources.FunctionResource`.
In the UI, a user can create such resource and provide it as a parameter to the step.
To use it, you can call the function with the note as an argument and return its output like so:

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output, Note
            from graphbook.utils import transform_function_string

            @step("Filter", event="__init__")
            def setup_fn(ctx, fn: str):
                ctx.fn = transform_function_string(ctx.fn)

            @step("Filter", event="forward_note")
            @param("fn", type="resource")
            @output("TRUE", "FALSE")
            def filter(ctx, note: Note):
                split_result = ctx.fn(note=note)
                if split_result:
                    return "TRUE"
                return "FALSE"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            from graphbook import Note
            from graphbook.utils import transform_function_string

            class Filter(Step):
                RequiresInput = True
                Parameters = {"fn": {"type": "resource"}}
                Outputs = ["TRUE", "FALSE"]
                Category = ""

                def __init__(self, fn):
                    super().__init__()
                    self.fn = transform_function_string(fn)

                def forward_note(self, note) -> str:
                    split_result = self.fn(note=note)
                    if split_result:
                        return "TRUE"
                    return "FALSE"

.. tip::

    The above Step is essentially already implemented as a built-in step in Graphbook :class:`graphbook.steps.Split`.

Delete Notes
============

Graphbook automatically keeps all output Notes in memory for visualization and monitoring, but sometimes, you don't want to retain filtered Notes at all.
By deleting them, you can conserve memory as long as you're sure you won't need them later in the workflow.

.. warning::

    You will not be able to view deleted notes in the Graphbook UI.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def filter(ctx, note: Note):
                if note['value'] > ctx.threshold:
                    return "good"
                return {} # Delete the note
    
    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def forward_note(self, note: Note) -> str:
                if note['value'] > self.threshold:
                    return "good"
               return {} # Delete the note

Clone and Versioning Notes
==========================

You may want to copy and create different notes based on a single note.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/clone_nodes.py

            from graphbook import step, param, output, Note
            import copy

            @step("Duplicate", event="forward_note")
            def filter(ctx, note: Note):
                note_v1 = copy.deepcopy(note)
                note_v1['version'] = 1
                note_v2 = copy.deepcopy(note)
                note_v2['version'] = 2

                return { "out": [note_v1, note_v2] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            from graphbook import Note
            import copy

            class Duplicate(Step):
                RequiresInput = True
                Parameters = {}
                Outputs = ["out"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def forward_note(self, note: Note) -> str:
                    note_v1 = copy.deepcopy(note)
                    note_v1['version'] = 1
                    note_v2 = copy.deepcopy(note)
                    note_v2['version'] = 2

                    return { "out": [note_v1, note_v2] }

Being able to generate new notes from a single note can be useful if the entity that the note describes can be split into two or more entities.
For example, if a note contains multiple images and the images may be associated with completely different entities, you can split them into those entities, so that we maintain a one-to-one relationship between the note and the entity.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output, Note
            import copy

            @step("FixImages", event="forward_note")
            @output("dog", "cat")
            def filter(ctx, note: Note):
                dog_images = []
                cat_images = []
                for image in note['images']:
                    if image['prediction'] == 'dog':
                        dog_images.append(image)
                    else:
                        cat_images.append(image)

                outputs = {}
                if len(dog_images) > 0:
                    note_dog = copy.deepcopy(note)
                    note_dog['images'] = dog_images
                    outputs["dog"] = [note_dog]
                if len(cat_images) > 0:
                    note_cat = copy.deepcopy(note)
                    note_cat['images'] = cat_images
                    outputs["cat"] = [note_cat]

                return outputs

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            from graphbook import Note

            class FixImages(Step):
                RequiresInput = True
                Parameters = {
                }
                Outputs = ["dog", "cat"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def forward_note(self, note: Note) -> str:
                    dog_images = []
                    cat_images = []
                    for image in note['images']:
                        if image['prediction'] == 'dog':
                            dog_images.append(image)
                        else:
                            cat_images.append(image)

                    outputs = {}
                    if len(dog_images) > 0:
                        note_dog = copy.deepcopy(note)
                        note_dog['images'] = dog_images
                        outputs["dog"] = [note_dog]
                    if len(cat_images) > 0:
                        note_cat = copy.deepcopy(note)
                        note_cat['images'] = cat_images
                        outputs["cat"] = [note_cat]

                    return outputs


.. meta::
    :description: How to filter data with Graphbook. Learn how we can filter data and handle data differently as they traverse different branches.
    :twitter:description: How to filter data with Graphbook. Learn how we can filter data and handle data differently as they traverse different branches.

.. _Filter:

Filter
######

Filtering data based on certain conditions and criteria is a common operation in data processing pipelines.
Graphbook provides a way to filter data and handle it differently as they traverse different branches.
Every step can have multiple output slots, and each slot can be used to route data to different parts of the graph.
You can route to a specific output slot with the :meth:`graphbook.steps.Step.route` method or event.

Basic Filtering
===============

.. tip::

    The default output slot is "out". To create other output slots, use the :func:`graphbook.output` decorator.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output

            @step("Filter", event="route")
            @param("threshold", type="number", default=0.5)
            @output("good", "junk")
            def filter(ctx, data: dict):
                if data['value'] > ctx.threshold:
                    return { "good": [data] }
                return { "junk": [data] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step

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

                def route(self, data: dict) -> str:
                    if data['value'] > ctx.threshold:
                        return { "good": [data] }
                    return { "junk": [data] }

Or otherwise, you can return just the output slot name as a short-hand way.


.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def filter(ctx, data: dict):
                if data['value'] > ctx.threshold:
                    return "good"
                return "junk"
    
    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def route(self, data: dict)) -> str:
                if data['value'] > self.threshold:
                    return "good"
                return "junk"

Filter Based on a Given Function
================================

You can also filter based on a given function with the resource :class:`graphbook.resources.FunctionResource`.
In the UI, a user can create such resource and provide it as a parameter to the step.
To use it, you can call the function as an argument and return its output like so:

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output
            from graphbook.utils import transform_function_string

            @step("Filter", event="__init__")
            def setup_fn(ctx, fn: str):
                ctx.fn = transform_function_string(ctx.fn)

            @step("Filter", event="route")
            @param("fn", type="resource")
            @output("TRUE", "FALSE")
            def filter(ctx, data: dict):
                split_result = ctx.fn(data)
                if split_result:
                    return "TRUE"
                return "FALSE"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            from graphbook.utils import transform_function_string

            class Filter(Step):
                RequiresInput = True
                Parameters = {"fn": {"type": "resource"}}
                Outputs = ["TRUE", "FALSE"]
                Category = ""

                def __init__(self, fn):
                    super().__init__()
                    self.fn = transform_function_string(fn)

                def route(self, data: dict) -> str:
                    split_result = self.fn(data)
                    if split_result:
                        return "TRUE"
                    return "FALSE"

.. tip::

    The above Step is essentially already implemented as a built-in step in Graphbook :class:`graphbook.steps.Split`.

Delete Data
===========

Graphbook automatically keeps all outputs in memory for visualization and monitoring, but sometimes, you don't want to retain filtered-out data at all.
By deleting them, you can conserve memory as long as you're sure you won't need them later in the workflow.

.. warning::

    You will not be able to view deleted data in the Graphbook UI.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def filter(ctx, data: dict):
                if data['value'] > ctx.threshold:
                    return "good"
                return {} # Frees it from memory
    
    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            ...

            def route(self, data: dict) -> str:
                if data['value'] > self.threshold:
                    return "good"
               return {} # Frees it from memory

Clone and Versioning Data
=========================

You may want to copy and create different objects based on a single objects.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/clone_nodes.py

            from graphbook import step, param, output
            import copy

            @step("Duplicate", event="route")
            def filter(ctx, data: dict):
                data_v1 = copy.deepcopy(data)
                data_v1['version'] = 1
                data_v2 = copy.deepcopy(data)
                data_v2['version'] = 2

                return { "out": [data_v1, data_v2] }

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step
            import copy

            class Duplicate(Step):
                RequiresInput = True
                Parameters = {}
                Outputs = ["out"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def route(self, data: dict) -> str:
                    data_v1 = copy.deepcopy(data)
                    data_v1['version'] = 1
                    data_v2 = copy.deepcopy(data)
                    data_v2['version'] = 2

                    return { "out": [data_v1, data_v2] }

Being able to generate more data from a single data point can be useful if the data point can be split into two or more entities.
For example, if an incoming data point contains multiple images and the images may be associated with completely different entities, you can split them into those entities, so that you can maintain a one-to-one relationship between the data and the entity.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook import step, param, output
            import copy

            @step("FixImages", event="route")
            @output("dog", "cat")
            def filter(ctx, data: dict):
                dog_images = []
                cat_images = []
                for image in data['images']:
                    if image['prediction'] == 'dog':
                        dog_images.append(image)
                    else:
                        cat_images.append(image)

                outputs = {}
                if len(dog_images) > 0:
                    dog = copy.deepcopy(data)
                    dog['images'] = dog_images
                    outputs["dog"] = [dog]
                if len(cat_images) > 0:
                    cat = copy.deepcopy(data)
                    cat['images'] = cat_images
                    outputs["cat"] = [cat]

                return outputs

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/filter_nodes.py

            from graphbook.steps import Step

            class FixImages(Step):
                RequiresInput = True
                Parameters = {
                }
                Outputs = ["dog", "cat"]
                Category = ""
                def __init__(self):
                    super().__init__()

                def route(self, data: dict) -> str:
                    dog_images = []
                    cat_images = []
                    for image in data['images']:
                        if image['prediction'] == 'dog':
                            dog_images.append(image)
                        else:
                            cat_images.append(image)

                    outputs = {}
                    if len(dog_images) > 0:
                        dog = copy.deepcopy(data)
                        dog['images'] = dog_images
                        outputs["dog"] = [dog]
                    if len(cat_images) > 0:
                        cat = copy.deepcopy(data)
                        cat['images'] = cat_images
                        outputs["cat"] = [cat]

                    return outputs


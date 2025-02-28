.. meta::
    :description: Learn how to prompt users during executing of your data processing pipelines. Prompting can be useful for collecting user input, labeling data, or for providing feedback during execution.
    :twitter:description: Learn how to prompt users during executing of your data processing pipelines. Prompting can be useful for collecting user input, labeling data, or for providing feedback during execution.

Prompts
#######

Graphbook supports human-in-the-loop steps with prompts.
Prompting can be useful for collecting user input, labeling data, or for providing feedback during execution.
You can make your own prompts with the help of the :func:`graphbook.prompt` decorator or by inheriting from the :class:`graphbook.steps.PromptStep` class.

.. seealso::

    :mod:`graphbook.prompts` - List of available prompts in Graphbook.

Prompt for Boolean Feedback
===========================

You can prompt users for boolean feedback with the :func:`graphbook.prompts.bool_prompt` function.
For example, you can ask users if an image is a dog and assign a label based on the user's response.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt
            from graphbook.prompts import bool_prompt

            @staticmethod
            def is_dog(data: dict):
                return bool_prompt(data, msg="Is this a dog?", show_images=True)

            @step("Prompts/CatVsDog")
            @prompt(is_dog)
            @staticmethod
            def label_images(data: dict, response: str):
                data["label"] = "dog" if response "Yes" else "cat"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook.prompts import bool_prompt

            class CatVsDog(PromptStep):
                RequiresInput = True
                Parameters = {
                }
                Outputs = ["out"]
                Category = "Prompts"
                def __init__(self):
                    super().__init__()

                def get_prompt(self, data: dict): # Override
                    return bool_prompt(data, show_images=True)
                
                def on_prompt_response(self, data: dict, response: Any): # Override
                    data["label"] = "dog" if response == "Yes" else "cat"


The function that is decorated is called when a response is received from the prompt.
The decorator accepts a function that returns a graphbook prompt object.
If no argument is passed to the decorator, by default, the step will always send a boolean prompt with the default parameters.

Prompt for Multiple Options
===========================

You can also prompt users for multiple options with the :func:`graphbook.prompts.selection_prompt` function.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt
            from graphbook.prompts import selection_prompt

            @staticmethod
            def select_option(data: dict):
                return selection_prompt(
                    data,
                    msg="Select an option",
                    options=["airplane", "bicycle", "car", "train", "junk data"],
                )

            @step("Prompts/Vehicles")
            @prompt(select_option)
            def select_option(ctx, data: dict, response: str):
                ctx.log("Selected option: ", response)
                data["label"] = response

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook.prompts import selection_prompt

            class Vehicles(PromptStep):
                RequiresInput = True
                Parameters = {
                }
                Outputs = ["out"]
                Category = "Prompts"
                def __init__(self):
                    super().__init__()

                def get_prompt(self, data: dict): # Override
                    return selection_prompt(
                        data,
                        msg="Select an option",
                        options=["airplane", "bicycle", "car", "train", "junk data"],
                    )
                
                def on_prompt_response(self, data: dict, response: Any): # Override
                    self.log("Selected option: ", response)
                    data["label"] = response

Conditional Prompts
===================

You can also conditionally prompt users based on the data inside of the data.
For example, you can prompt users only if the model is not confident about the prediction based on its logits
or by some other metric.
To not prompt the user on a given data, all you have to do is return ``None``.

.. tab-set::

    .. tab-item:: function

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt
            from graphbook.prompts import bool_prompt

            @staticmethod
            def is_dog(data: dict):
                if data["model_confidence"] < 0.8:
                    return bool_prompt(data, msg=f"Model predicted {data['label']}. Is this correct?", show_images=True)
                return None

            @step("Prompts/ConditionalCatVsDog")
            @prompt(is_dog)
            @staticmethod
            def label_images(data: dict, response: str):
                if response == "No":
                    data["label"] = "dog" if data["label"] == "cat" else "cat"

    .. tab-item:: class

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook.prompts import bool_prompt

            class ConditionalCatVsDog(PromptStep):
                RequiresInput = True
                Parameters = {
                }
                Outputs = ["out"]
                Category = "Prompts"
                def __init__(self):
                    super().__init__()

                def get_prompt(self, data: dict): # Override
                    if data["model_confidence"] < 0.8:
                        return bool_prompt(data, msg=f"Model predicted {data['label']}. Is this correct?", show_images=True)
                    return None
                
                def on_prompt_response(self, data: dict, response: Any): # Override
                    if response == "No":
                        data["label"] = "dog" if data["label"] == "cat" else "cat"

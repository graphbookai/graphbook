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

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt, Note
            from graphbook.prompts import bool_prompt

            @staticmethod
            def is_dog(note: Note):
                return bool_prompt(note, msg="Is this a dog?", show_images=True)

            @step("Prompts/CatVsDog")
            @prompt(is_dog)
            @staticmethod
            def label_images(note: Note, response: str):
                note["label"] = "dog" if response "Yes" else "cat"

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

                def get_prompt(self, note: Note): # Override
                    return bool_prompt(note, show_images=True)
                
                def on_prompt_response(self, note: Note, response: Any): # Override
                    note["label"] = "dog" if response == "Yes" else "cat"


The function that is decorated is called when a response is received from the prompt.
The decorator accepts a function that returns a graphbook prompt object.
If no argument is passed to the decorator, by default, the step will always send a boolean prompt with the default parameters.

Prompt for Multiple Options
===========================

You can also prompt users for multiple options with the :func:`graphbook.prompts.selection_prompt` function.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt, Note
            from graphbook.prompts import selection_prompt

            @staticmethod
            def select_option(note: Note):
                return selection_prompt(
                    note,
                    msg="Select an option",
                    options=["airplane", "bicycle", "car", "train", "junk data"],
                )

            @step("Prompts/Vehicles")
            @prompt(select_option)
            def select_option(ctx, note: Note, response: str):
                ctx.log("Selected option: ", response)
                note["label"] = response

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

                def get_prompt(self, note: Note): # Override
                    return selection_prompt(
                        note,
                        msg="Select an option",
                        options=["airplane", "bicycle", "car", "train", "junk data"],
                    )
                
                def on_prompt_response(self, note: Note, response: Any): # Override
                    self.log("Selected option: ", response)
                    note["label"] = response

Conditional Prompts
===================

You can also conditionally prompt users based on the data inside of the note.
For example, you can prompt users only if the model is not confident about the prediction based on its logits
or by some other metric.
To not prompt the user on a given note, all you have to do is return ``None``.

.. tab-set::

    .. tab-item:: function (recommended)

        .. code-block:: python
            :caption: custom_nodes/prompted_nodes.py

            from graphbook import step, prompt, Note
            from graphbook.prompts import bool_prompt

            @staticmethod
            def is_dog(note: Note):
                if note["model_confidence"] < 0.8:
                    return bool_prompt(note, msg=f"Model predicted {note['label']}. Is this correct?", show_images=True)
                return None

            @step("Prompts/ConditionalCatVsDog")
            @prompt(is_dog)
            @staticmethod
            def label_images(note: Note, response: str):
                if response == "No":
                    note["label"] = "dog" if note["label"] == "cat" else "cat"

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

                def get_prompt(self, note: Note): # Override
                    if note["model_confidence"] < 0.8:
                        return bool_prompt(note, msg=f"Model predicted {note['label']}. Is this correct?", show_images=True)
                    return None
                
                def on_prompt_response(self, note: Note, response: Any): # Override
                    if response == "No":
                        note["label"] = "dog" if note["label"] == "cat" else "cat"

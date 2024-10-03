.. meta::
    :description: Graphbook Reference Documentation for Step classes.
    :twitter:description: Graphbook Reference Documentation for Step classes.

Steps
#####

.. rst-class:: lead

    Below contains detailed reference documentation for working with Steps in Graphbook. You can create steps with decorators and functions or by extending any of the following base classes.

.. seealso::

    Decorators :func:`graphbook.step`, :func:`graphbook.batch`, :func:`graphbook.source`, and :func:`graphbook.prompt` to create steps in a functional way.

.. autoclass:: graphbook.steps.Step
    :members:

.. autoclass:: graphbook.steps.BatchStep
    :members:

.. autoclass:: graphbook.steps.PromptStep
    :members:

.. seealso::
    
    :mod:`graphbook.prompts` for available user prompts.

.. autoclass:: graphbook.steps.SourceStep
    :members:

.. autoclass:: graphbook.steps.GeneratorSourceStep
    :members:

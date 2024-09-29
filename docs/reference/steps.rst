.. meta::
    :description: Graphbook Reference Documentation for steps
    :twitter:description: Graphbook Reference Documentation for steps

Steps
#####

.. rst-class:: lead

    Below contains detailed reference documentation for working with Steps in Graphbook. You can create steps with decorators and functions or by extending any of the following base classes.

.. seealso::

    Decorators that can define the extendible step classes: :ref:`step decorator`, :ref:`batch decorator`, :ref:`source decorator`, :ref:`prompt decorator`

.. autoclass:: graphbook.steps.Step
    :members:

.. autoclass:: graphbook.steps.BatchStep
    :members:

.. autoclass:: graphbook.steps.PromptStep
    :members:

.. autoclass:: graphbook.steps.SourceStep
    :members:

.. autoclass:: graphbook.steps.GeneratorSourceStep
    :members:

.. _Installing:

Installing
##########

Requirements
============

* Python 3.10+

Install from PyPI
=================

.. code-block:: bash

    pip install nebo

Or with `uv <https://docs.astral.sh/uv/>`_:

.. code-block:: bash

    uv add nebo

Quick Start
===========

Run a pipeline in local mode (Rich terminal display, no daemon needed):

.. code-block:: bash

    python my_pipeline.py

Or use the daemon for persistent observability with a web UI:

.. code-block:: bash

    nebo serve -d
    nebo run my_pipeline.py

Then visit http://localhost:7861 to see the UI.


Install from Source
===================

.. _uv: https://docs.astral.sh/uv/
.. _Node.js: https://nodejs.org/

Installing from source requires uv_ and Node.js_.

.. code-block:: bash

    git clone https://github.com/graphbookai/nebo.git
    cd nebo
    uv sync --all-groups

To build the web UI from source:

.. code-block:: bash

    cd ui
    npm ci
    npm run build
    cp -r dist/* ../nebo/server/static/

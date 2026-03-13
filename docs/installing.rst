.. _Installing:

Installing
##########

Requirements
============
#. Python 3.10+

Install from PyPI
=================

#. ``pip install graphbook``
#. ``graphbook``
#. Visit http://localhost:8005

Install with Docker
===================

#. Pull and run the latest image

   .. code-block:: bash

       docker run --rm -p 8005:8005 -v $PWD/workflows:/app/workflows rsamf/graphbook:latest

#. Visit http://localhost:8005


Install from Source
===================

.. note::

    If you wish to run graphbook in development mode, visit the :ref:`contributing` section.

.. _uv: https://docs.astral.sh/uv/
.. _Node.js: https://nodejs.org/

Installing from source requires uv_ and Node.js_.

#. Clone the repository
#. ``cd graphbook``
#. ``make web``
#. ``uv sync``
#. cd into the directory you want to create your workflows in
#. ``<PATH_TO_REPO>/scripts/graphbook``

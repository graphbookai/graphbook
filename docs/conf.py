# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Graphbook'
copyright = '2024, Graphbook AI'
author = 'Graphbook AI'

import os
import sys
sys.path.insert(0, os.path.abspath('../src'))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc',
              'sphinx.ext.coverage',
              'sphinx.ext.napoleon',
              'sphinxawesome_theme']

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
html_theme_options = {
    "logo_light": "_static/graphbook.png",
    "logo_dark": "_static/graphbook.png",
    "show_scrolltop": True,
    'extra_header_link_icons': {
        'our github repo': {
            'link': 'https://github.com/graphbookai/graphbook',
            'icon': '<svg fill="currentColor" height="26px" style="margin-top:-2px;display:inline" viewBox="0 0 45 44" xmlns="http://www.w3.org/2000/svg"><path clip-rule="evenodd" d="M22.477.927C10.485.927.76 10.65.76 22.647c0 9.596 6.223 17.736 14.853 20.608 1.087.2 1.483-.47 1.483-1.047 0-.516-.019-1.881-.03-3.693-6.04 1.312-7.315-2.912-7.315-2.912-.988-2.51-2.412-3.178-2.412-3.178-1.972-1.346.149-1.32.149-1.32 2.18.154 3.327 2.24 3.327 2.24 1.937 3.318 5.084 2.36 6.321 1.803.197-1.403.759-2.36 1.379-2.903-4.823-.548-9.894-2.412-9.894-10.734 0-2.37.847-4.31 2.236-5.828-.224-.55-.969-2.759.214-5.748 0 0 1.822-.584 5.972 2.226 1.732-.482 3.59-.722 5.437-.732 1.845.01 3.703.25 5.437.732 4.147-2.81 5.967-2.226 5.967-2.226 1.185 2.99.44 5.198.217 5.748 1.392 1.517 2.232 3.457 2.232 5.828 0 8.344-5.078 10.18-9.916 10.717.779.67 1.474 1.996 1.474 4.021 0 2.904-.027 5.247-.027 5.96 0 .58.392 1.256 1.493 1.044C37.981 40.375 44.2 32.24 44.2 22.647c0-11.996-9.726-21.72-21.722-21.72" fill="currentColor" fill-rule="evenodd"></path></svg>'
        }
    }
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_favicon = '_static/graphbook_32.png'
html_title = 'Graphbook - ML Workflow Framework'
html_permalinks_icon = \
"""
<svg height="1em" viewBox="0 0 24 24" width="1em" xmlns="http://www.w3.org/2000/svg">
<path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"></path>
</svg>
"""
html_theme = 'sphinxawesome_theme'
html_static_path = ['_static']
html_context = {
    'og_image': 'https://cdn.prod.website-files.com/6620137e5938f28a7e4eef8a/66aebc5f3b8d7345af42babe_GB%20OpenGraph.png',
    'og_description': 'Graphbook is a framework for building efficient, interactive DAG-structured ML workflows composed of nodes which can be implemented in Python. It provides common ML processing features and a web UI to assemble, monitor, and execute data processing pipelines.'
}

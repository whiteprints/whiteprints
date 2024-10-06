.. SPDX-FileCopyrightText: © 2015 Read the Docs, Inc
.. SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
..
.. SPDX-License-Identifier: MIT

📖 API Reference
================

This section contains auto-generated API reference documentation.

.. toctree::
   :titlesonly:

   {% for page in pages|selectattr("is_top_level_object") %}
   {{ page.include_path }}
   {% endfor %}

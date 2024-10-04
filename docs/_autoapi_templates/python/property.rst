.. SPDX-FileCopyrightText: © 2015 Read the Docs, Inc
.. SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
..
.. SPDX-License-Identifier: MIT

{% if obj.display %}
   {% if is_own_page %}
{{ obj.id }}
{{ "=" * obj.id | length }}

   {% endif %}
.. py:property:: {% if is_own_page %}{{ obj.id}}{% else %}{{ obj.short_name }}{% endif %}
   {% if obj.annotation %}

   :type: {{ obj.annotation }}
   {% endif %}
   {% for property in obj.properties %}

   :{{ property }}:
   {% endfor %}

   {% if obj.docstring %}
   {{ obj.docstring|indent(3) }}
   {% endif %}
{% endif %}

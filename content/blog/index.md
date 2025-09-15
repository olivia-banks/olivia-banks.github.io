---
title: The Blog
date: 2025-01-29
type: index
---
You can find entries in my blog below. I don't post very often, but when I do,
I try to make it as informational as possible.

<div style="margin-top: 2em; margin-bottom: 2em;">
{% for post in get_from_registry(registry, 'content/blog') %}
{{ loop.index0 }}. [{{ post.metadata.title }}](</{{ post_url(post) }}>) - {{ post.metadata.description }}
{% endfor %}
</div>

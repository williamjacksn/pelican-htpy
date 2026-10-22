# pelican-htpy

pelican-htpy lets you render a Pelican site with Python functions that return htpy
elements. Pelican continues to read content, build template contexts, paginate
articles, generate feeds, and copy static files.

## Installation

The package requires Python 3.14 or later. Install it in the same environment as
your Pelican site:

```console
python -m pip install pelican-htpy
```

If you manage your site with uv, add the package to your project:

```console
uv add pelican-htpy
```

## Configuration

Add `"htpy"` to your `PLUGINS` setting and define `HTPY_TEMPLATES` in
`pelicanconf.py`. Each key is a template name, and each value is a synchronous
callable that accepts a context dictionary and returns an htpy element.

The following example renders articles and pages with their content and renders
article listings with links. It uses one listing component for the standard
listing templates. You can replace each mapping with a separate component as
your site grows.

```python
import htpy
from markupsafe import Markup


def layout(context, title, body):
    return htpy.html(lang="en")[
        htpy.head[
            htpy.meta(charset="utf-8"),
            htpy.title[title],
        ],
        htpy.body[
            htpy.header[htpy.h1[context["SITENAME"]]],
            htpy.main[body],
        ],
    ]


def content_template(context):
    item = context.get("article", context.get("page"))
    return layout(
        context,
        item.title,
        [htpy.h1[item.title], Markup(item.content)],
    )


def listing_template(context):
    page = context.get("articles_page")
    articles = page.object_list if page is not None else context["articles"]
    return layout(
        context,
        context["SITENAME"],
        htpy.ul[
            [
                htpy.li[
                    htpy.a(href=f"{context['SITEURL']}/{article.url}")[article.title]
                ]
                for article in articles
            ]
        ],
    )


PLUGINS = ["htpy"]

HTPY_TEMPLATES = {
    "article": content_template,
    "page": content_template,
    "index": listing_template,
    "archives": listing_template,
    "author": listing_template,
    "authors": listing_template,
    "category": listing_template,
    "categories": listing_template,
    "tag": listing_template,
    "tags": listing_template,
    "period_archives": listing_template,
}
```

If you already configure other plugins, keep their entries in `PLUGINS`. Build
your site with the usual Pelican command:

```console
pelican content -s pelicanconf.py
```

## Template names and contexts

Register every template that your enabled outputs require. Use names such as
`"article"` and `"index"` without a file extension. If content specifies a custom
template, register that name as well. For example, content with
`:template: special` in reStructuredText requires a `"special"` entry in
`HTPY_TEMPLATES`.

Components receive Pelican's context dictionary, including settings such as
`SITENAME` and `SITEURL`. Article templates receive `context["article"]`, and page
templates receive `context["page"]`. Listing templates receive
`context["articles"]`. When Pelican paginates a listing, use
`context["articles_page"].object_list` to render only the current page's articles.
Add navigation links using Pelican's pagination context if your site needs them.

The context also includes `output_file`. When `RELATIVE_URLS` is enabled, Pelican
adjusts `SITEURL` for the output file's location before calling the component.

htpy escapes ordinary strings. The example wraps `item.content` in `Markup`
because Pelican has already rendered it as HTML. Only mark HTML as safe when you
trust its source.

## Additional template pages

You can use `TEMPLATE_PAGES` to render a registered component to a specific path.
The source name must match a key in `HTPY_TEMPLATES`:

```python
def welcome_template(context):
    return layout(context, "Welcome", htpy.p["Welcome to this site."])


HTPY_TEMPLATES["welcome"] = welcome_template
TEMPLATE_PAGES = {"welcome": "extras/welcome.html"}
```

## Configuration errors

If `HTPY_TEMPLATES` is absent or set to `None`, the plugin leaves Pelican's normal
template loading in place. When the setting is a mapping, it replaces template
lookup for articles, pages, and template pages. Missing names raise
`PelicanTemplateNotFound`; they do not fall back to Jinja templates. An empty
mapping therefore fails when Pelican requests a template.

The setting must be a mapping with string keys and callable values. Invalid
entries raise `TypeError`. Components must run synchronously.

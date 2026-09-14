from pathlib import Path
from typing import Any
from unittest.mock import patch

import htpy
import pytest
from markupsafe import Markup
from pelican.generators import ArticlesGenerator, Generator, PelicanTemplateNotFound
from pelican.settings import read_settings

from pelican import Pelican, signals

# Pelican uses pkgutil.extend_path to discover this editable namespace plugin.
from pelican.plugins.htpy import (  # ty: ignore[unresolved-import]
    HtpyTemplate,
    configure_generator,
)


def test_render_escaping_and_markup() -> None:
    # Intentionally trust fixture HTML to test preservation of explicit markup.
    template = HtpyTemplate(lambda c: htpy.main[c["text"], Markup(c["html"])])  # noqa: S704
    assert template.render({"text": "<unsafe>", "html": "<b>body</b>"}) == (
        "<main>&lt;unsafe&gt;<b>body</b></main>"
    )


def test_complete_build(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    for number in (1, 2):
        (content / f"post{number}.rst").write_text(
            f"Post {number}\n======\n:date: 2026-01-0{number}\n"
            ":category: News\n:tags: example\n:author: Writer\n"
            ":template: special\n\nA **bold** body.\n",
            encoding="utf-8",
        )
    (content / "pages").mkdir()
    (content / "pages" / "about.rst").write_text(
        "About\n=====\n\nAbout body.\n", encoding="utf-8"
    )
    (content / "asset.txt").write_text("asset", encoding="utf-8")
    seen = {}

    def component(context: dict[str, Any]) -> htpy.Element:
        seen[context["output_file"]] = context.copy()
        item = context.get("article", context.get("page"))
        if item is not None:
            # Pelican renders this HTML from the trusted test content above.
            body = Markup(item.content)  # noqa: S704
            return htpy.html[htpy.body[htpy.h1[item.title], body]]
        page = context.get("articles_page")
        items = page.object_list if page is not None else context["articles"]
        return htpy.html[htpy.body[[htpy.h1[item.title] for item in items]]]

    settings = read_settings(
        override={
            "PATH": str(content),
            "OUTPUT_PATH": str(tmp_path / "output"),
            "PLUGINS": ["htpy"],
            "TIMEZONE": "UTC",
            "SITEURL": "https://example.com",
            "RELATIVE_URLS": True,
            "DEFAULT_PAGINATION": 1,
            "STATIC_PATHS": ["asset.txt"],
            "FEED_ALL_ATOM": "feeds/all.atom.xml",
            "TEMPLATE_PAGES": {"landing": "nested/welcome.html"},
            "HTPY_TEMPLATES": dict.fromkeys(
                [
                    "special",
                    "page",
                    "index",
                    "archives",
                    "authors",
                    "categories",
                    "tags",
                    "author",
                    "category",
                    "tag",
                    "landing",
                ],
                component,
            ),
        }
    )
    written = []

    def on_written(sender: str, **_kwargs: object) -> None:
        written.append(Path(sender).name)

    signals.content_written.connect(on_written)
    try:
        # Any accidental use of core template lookup must fail the build.
        with (
            patch.object(Generator, "get_template", side_effect=AssertionError),
            patch("jinja2.Environment.get_template", side_effect=AssertionError),
        ):
            Pelican(settings).run()
    finally:
        signals.content_written.disconnect(on_written)
        signals.generator_init.disconnect(configure_generator)

    output = tmp_path / "output"
    assert "<strong>bold</strong>" in (output / "post-1.html").read_text()
    assert (output / "pages/about.html").exists()
    assert len(seen["index.html"]["articles_page"].object_list) == 1
    assert len(seen["index2.html"]["articles_page"].object_list) == 1
    assert seen["nested/welcome.html"]["SITEURL"] == ".."
    assert (output / "feeds/all.atom.xml").exists()
    assert (output / "asset.txt").read_text() == "asset"
    assert "welcome.html" in written
    assert (output / "tag/example.html").exists()
    assert (output / "category/news.html").exists()


@pytest.mark.parametrize("registry", [[], {"article": 42}, {1: lambda _c: htpy.html}])
def test_invalid_registry(registry: object) -> None:

    generator = object.__new__(ArticlesGenerator)
    generator.settings = {"HTPY_TEMPLATES": registry}
    with pytest.raises(TypeError, match="HTPY_TEMPLATES"):
        configure_generator(generator)


def test_missing_template_and_no_setting() -> None:

    generator = object.__new__(ArticlesGenerator)
    generator.settings = {}
    configure_generator(generator)
    assert "get_template" not in generator.__dict__
    generator.settings["HTPY_TEMPLATES"] = {}
    configure_generator(generator)
    with pytest.raises(PelicanTemplateNotFound, match="'article'"):
        generator.get_template("article")

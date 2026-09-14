"""Render Pelican output with synchronous htpy components."""

from collections.abc import Callable, Mapping
from typing import Any

from pelican.generators import (
    ArticlesGenerator,
    Generator,
    PagesGenerator,
    PelicanTemplateNotFound,
    TemplatePagesGenerator,
)
from pelican.writers import Writer

from htpy import Renderable
from pelican import signals

Component = Callable[[dict[str, Any]], Renderable]


class HtpyTemplate:
    """Implement the template interface consumed by Pelican's writer."""

    def __init__(self, component: Component) -> None:
        self.component = component

    def render(self, context: dict[str, Any]) -> str:
        return str(self.component(context))


def configure_generator(generator: Generator) -> None:
    """Install instance-local lookup without changing Pelican's classes."""
    if not isinstance(
        generator, (ArticlesGenerator, PagesGenerator, TemplatePagesGenerator)
    ):
        return

    # Signal connections survive subsequent builds in the same Python process.
    # Leave builds without this setting alone.
    components = generator.settings.get("HTPY_TEMPLATES")
    if components is None:
        return
    if not isinstance(components, Mapping):
        raise TypeError("HTPY_TEMPLATES must be a mapping of names to callables")
    templates = {}
    for name, component in components.items():
        if not isinstance(name, str) or not callable(component):
            raise TypeError("HTPY_TEMPLATES must map string names to callables")
        templates[name] = HtpyTemplate(component)

    def get_template(name: str) -> HtpyTemplate:
        try:
            return templates[name]
        except KeyError:
            raise PelicanTemplateNotFound(
                f"No htpy component registered for {name!r} in HTPY_TEMPLATES"
            ) from None

    # Instance attributes hold plain callables; ty expects the class method type.
    generator.get_template = get_template  # ty: ignore[invalid-assignment]

    if isinstance(generator, TemplatePagesGenerator):
        # Core TEMPLATE_PAGES bypasses get_template and accesses Jinja's loader.
        def generate_output(writer: Writer) -> None:
            for source, destination in generator.settings["TEMPLATE_PAGES"].items():
                writer.write_file(
                    destination,
                    get_template(source),
                    generator.context,
                    generator.settings["RELATIVE_URLS"],
                    override_output=True,
                    url="",
                )

        # As above, this closure intentionally replaces a bound method.
        generator.generate_output = generate_output  # ty: ignore[invalid-assignment]


def register() -> None:
    signals.generator_init.connect(configure_generator)


def main() -> None:
    print("Hello from pelican-htpy!")

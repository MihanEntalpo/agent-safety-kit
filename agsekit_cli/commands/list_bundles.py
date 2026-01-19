from __future__ import annotations

import click

from ..i18n import tr
from ..vm_bundle_definitions import BUNDLE_DEFINITIONS


@click.command(name="list-bundles", help=tr("list_bundles.command_help"))
def list_bundles_command() -> None:
    """List supported VM install bundles."""
    for name in sorted(BUNDLE_DEFINITIONS):
        bundle = BUNDLE_DEFINITIONS[name]
        extras = []
        if bundle.dependencies:
            extras.append(tr("list_bundles.dependencies", deps=", ".join(bundle.dependencies)))
        if bundle.supports_version:
            extras.append(tr("list_bundles.versioned"))
        suffix = f" ({'; '.join(extras)})" if extras else ""
        click.echo(tr("list_bundles.line", name=bundle.name, description=bundle.description, suffix=suffix))

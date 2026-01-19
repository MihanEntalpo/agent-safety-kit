from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .i18n import tr
from .vm_bundle_definitions import BUNDLE_DEFINITIONS


@dataclass(frozen=True)
class BundleRequest:
    name: str
    version: Optional[str]
    raw: str


@dataclass(frozen=True)
class ResolvedBundle:
    name: str
    version: Optional[str]
    script: Path
    raw: str


def parse_bundle(raw: str, vm_name: str) -> BundleRequest:
    text = raw.strip()
    if not text:
        raise ValueError(tr("config.install_empty", vm_name=vm_name))

    if ":" in text:
        name, version = text.split(":", 1)
        name = name.strip()
        version = version.strip()
        if not name:
            raise ValueError(tr("config.install_missing_name", vm_name=vm_name))
        if not version:
            raise ValueError(tr("config.install_missing_version", vm_name=vm_name, bundle=name))
    else:
        name, version = text, None

    definition = BUNDLE_DEFINITIONS.get(name)
    if not definition:
        raise ValueError(tr("config.install_unknown_bundle", vm_name=vm_name, bundle=name))
    if version and not definition.supports_version:
        raise ValueError(tr("config.install_version_not_supported", vm_name=vm_name, bundle=name))

    return BundleRequest(name=name, version=version, raw=text)


def normalize_install_bundles(raw_entry: object, vm_name: str) -> list[str]:
    if raw_entry is None:
        return []
    if not isinstance(raw_entry, list):
        raise ValueError(tr("config.install_not_list", vm_name=vm_name))

    bundles: list[str] = []
    for index, raw in enumerate(raw_entry):
        if not isinstance(raw, str):
            raise ValueError(tr("config.install_not_string", vm_name=vm_name, index=index))
        cleaned = raw.strip()
        parse_bundle(cleaned, vm_name)
        bundles.append(cleaned)

    return bundles


def resolve_bundles(requested: Sequence[str], vm_name: str) -> list[ResolvedBundle]:
    resolved: list[ResolvedBundle] = []
    seen: set[str] = set()

    def add_bundle(bundle: BundleRequest) -> None:
        key = f"{bundle.name}:{bundle.version}" if bundle.version else bundle.name
        if key in seen:
            return
        definition = BUNDLE_DEFINITIONS[bundle.name]
        for dep in definition.dependencies:
            add_bundle(BundleRequest(name=dep, version=None, raw=dep))
        resolved.append(
            ResolvedBundle(
                name=bundle.name,
                version=bundle.version,
                script=definition.script,
                raw=bundle.raw,
            )
        )
        seen.add(key)

    for raw in requested:
        add_bundle(parse_bundle(raw, vm_name))

    return resolved

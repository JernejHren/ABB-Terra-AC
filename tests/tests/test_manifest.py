"""Invariants Home Assistant expects for custom integration discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from awesomeversion import AwesomeVersion, AwesomeVersionException
from awesomeversion.strategy import AwesomeVersionStrategy

from custom_components.abb_terra_ac.const import DOMAIN

_MANIFEST = Path(__file__).resolve().parents[1] / "custom_components" / "abb_terra_ac" / "manifest.json"


def test_manifest_json_parses() -> None:
    raw = _MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert isinstance(manifest, dict)


def test_manifest_domain_matches_package() -> None:
    """Loader indexes custom integrations by manifest[\"domain\"] — must match const DOMAIN."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("domain") == DOMAIN


def test_manifest_version_accepted_by_home_assistant() -> None:
    """Custom integrations without a valid version are blocked (loader.resolve_from_root)."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    version = manifest.get("version")
    assert version is not None
    try:
        AwesomeVersion(
            version,
            ensure_strategy=[
                AwesomeVersionStrategy.CALVER,
                AwesomeVersionStrategy.SEMVER,
                AwesomeVersionStrategy.SIMPLEVER,
                AwesomeVersionStrategy.BUILDVER,
                AwesomeVersionStrategy.PEP440,
            ],
        )
    except AwesomeVersionException as err:
        pytest.fail(f"Invalid manifest version {version!r}: {err}")

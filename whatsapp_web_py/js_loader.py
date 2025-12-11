from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict

BASE = Path(__file__).resolve().parent / "js"


def _load(path: str) -> str:
    target = BASE / path
    return target.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def load_scripts() -> Dict[str, str]:
    """
    Lê os scripts de injeção JS reutilizados do projeto original.
    Retorna um dict com as chaves:
    auth_store, legacy_auth_store, store, legacy_store, utils, moduleraid.
    """
    return {
        "auth_store": _load("Injected/AuthStore/AuthStore.js"),
        "legacy_auth_store": _load("Injected/AuthStore/LegacyAuthStore.js"),
        "store": _load("Injected/Store.js"),
        "legacy_store": _load("Injected/LegacyStore.js"),
        "utils": _load("Injected/Utils.js"),
        "moduleraid": _load("moduleraid.js"),
    }


def wrap_commonjs(source: str, export_name: str) -> str:
    """Transforma um módulo CommonJS simples em um IIFE executável no navegador."""
    return f"(function(){{ const exports = {{}}; {source}; return exports.{export_name} && exports.{export_name}(); }})();"

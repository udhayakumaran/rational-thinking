"""Configuration loading (YAML -> dicts -> typed objects)."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with open(p) as f:
        return yaml.safe_load(f) or {}


def load_config(path: str | Path = "config/default.yaml") -> dict:
    return load_yaml(path)


def db_url(cfg: dict) -> str:
    url = cfg["database"]["url"]
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{ROOT / rel}"
    return url

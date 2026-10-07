"""V1 must not be able to place real orders. Scan the code for order-routing calls."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    r"place_?order", r"modify_?order", r"cancel_?order", r"placeorder", r"order_place", r"submit_?order",
    r"/orders/regular", r"api\.kite\.trade/orders", r"api\.upstox\.com/v\d/order", r"/v2/orders",
    r"live_trading\s*=\s*True", r"enable_live",
]


def test_no_order_routing_code():
    hits = []
    for p in list((ROOT / "optlab").rglob("*.py")) + list((ROOT / "scripts").rglob("*.py")):
        text = p.read_text().lower()
        for pat in FORBIDDEN:
            if re.search(pat, text):
                hits.append(f"{p.relative_to(ROOT)}: {pat}")
    assert not hits, f"order-routing code found: {hits}"


def test_config_has_no_live_mode():
    cfg = (ROOT / "config" / "default.yaml").read_text()
    assert "mode: paper_only" in cfg and "live" not in cfg.split("mode: paper_only")[0]

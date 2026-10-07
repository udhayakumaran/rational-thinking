import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from optlab.data.synthetic import SyntheticConfig, SyntheticMarketData  # noqa: E402


@pytest.fixture(scope="session")
def md_small():
    """~4 months of deterministic synthetic data (negative control)."""
    return SyntheticMarketData(SyntheticConfig(start=date(2024, 1, 1), end=date(2024, 4, 30), seed=11))


@pytest.fixture(scope="session")
def md_edge():
    return SyntheticMarketData(SyntheticConfig(start=date(2024, 1, 1), end=date(2024, 6, 30), seed=5,
                                               edge_strength=0.08))

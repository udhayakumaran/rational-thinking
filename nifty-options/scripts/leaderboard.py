#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd  # noqa: E402
from optlab.config import db_url, load_config  # noqa: E402
from optlab.db.session import session_factory  # noqa: E402
from optlab.research.experiments import Registry  # noqa: E402
from optlab.research.leaderboard import leaderboard  # noqa: E402

pd.set_option("display.width", 250, "display.max_columns", 30)
print(leaderboard(Registry(session_factory(db_url(load_config())))).to_string())

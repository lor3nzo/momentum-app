import os
import sys
import numpy as np
import pandas as pd
from backend.momentum import compute_scores

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend import compute_scores


def test_compute_scores_positive_momentum():
    prices = pd.DataFrame({"close": list(range(1, 320))})
    scores, breadth = compute_scores({"AAA": prices})
    row = scores[scores["symbol"] == "AAA"].iloc[0]
    assert row["MomentumScore"] > 0
    assert row["enter_long"]
    prices_up = pd.DataFrame({"close": np.linspace(1, 400, 320)})
    prices_down = pd.DataFrame({"close": np.linspace(400, 1, 320)})
    scores, breadth = compute_scores({"AAA": prices_up, "BBB": prices_down})
    row_up = scores[scores["symbol"] == "AAA"].iloc[0]
    row_down = scores[scores["symbol"] == "BBB"].iloc[0]
    assert row_up["MomentumScore"] > row_down["MomentumScore"]
    assert row_up["enter_long"]

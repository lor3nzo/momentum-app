import pandas as pd
from backend.momentum import compute_scores

def test_compute_scores_positive_momentum():
    prices = pd.DataFrame({"close": list(range(1, 320))})
    scores, breadth = compute_scores({"AAA": prices})
    row = scores[scores["symbol"] == "AAA"].iloc[0]
    assert row["MomentumScore"] > 0
    assert row["enter_long"]

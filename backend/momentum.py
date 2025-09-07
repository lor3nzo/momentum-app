from typing import Dict, Tuple
import numpy as np
import pandas as pd

def _ewma_vol(log_rets, lam=0.94):
    var = 0.0
    tail = log_rets[-252:] if len(log_rets) >= 252 else log_rets
    for r in tail:
        var = lam * var + (1 - lam) * (r ** 2)
    return float(np.sqrt(var * 252))

def compute_scores(universe_prices: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, float]:
    rows = []
    for sym, df in universe_prices.items():
        if df is None or df.shape[0] < 260:
            rows.append((sym, np.nan, np.nan, np.nan, 0, 0, 0, np.nan))
            continue
        close = df["close"].astype(float).values
        try:
            r_12_1 = (close[-22] / close[-253]) - 1.0
            r_6_1  = (close[-22] / close[-127]) - 1.0
            r_3_1  = (close[-22] / close[-64])  - 1.0
        except Exception:
            r_12_1, r_6_1, r_3_1 = np.nan, np.nan, np.nan

        s = pd.Series(close)
        ma50 = float(s.rolling(50).mean().iloc[-1])
        ma200 = float(s.rolling(200).mean().iloc[-1])
        trend_state = 1 if (ma50 > ma200) else 0

        try:
            ts_mom = float(np.sign(np.log(close[-1] / close[-127])))
        except Exception:
            ts_mom = 0.0
        gate = 1 if (trend_state == 1 and ts_mom > 0) else 0

        rets = np.diff(np.log(close))
        sigma = _ewma_vol(rets) if len(rets) > 10 else np.nan

        rows.append((sym, r_12_1, r_6_1, r_3_1, trend_state, ts_mom, gate, sigma))

    raw = pd.DataFrame(rows, columns=[
        "symbol","r_12_1","r_6_1","r_3_1","trend50>200","ts_mom_sign","gate","ann_vol"
    ])

    for col in ["r_12_1","r_6_1","r_3_1"]:
        x = raw[col].astype(float)
        q1, q99 = x.quantile(0.01), x.quantile(0.99)
        raw[col] = x.clip(q1, q99)

    def zscore(series: pd.Series) -> pd.Series:
        m = series.mean(skipna=True)
        sd = series.std(skipna=True)
        if sd and not pd.isna(sd) and sd > 0:
            return (series - m) / sd
        return pd.Series(np.zeros(len(series)), index=series.index)

    raw["z_12_1"] = zscore(raw["r_12_1"])
    raw["z_6_1"]  = zscore(raw["r_6_1"])
    raw["z_3_1"]  = zscore(raw["r_3_1"])

    raw["Z_mom"] = 0.50*raw["z_12_1"] + 0.30*raw["z_6_1"] + 0.20*raw["z_3_1"]

    breadth = float(np.nanmean((raw["Z_mom"] > 0).astype(float))) if len(raw) > 0 else float("nan")

    def scale01(x, lo, hi):
        return np.clip((x - lo) / (hi - lo), 0, 1)

    S1 = scale01(raw["Z_mom"].values, -2, 2) * 100.0
    S2 = (raw["gate"].values > 0).astype(float) * 100.0

    b_clip = np.clip(breadth, 0.4, 0.9) if not (breadth != breadth) else 0.4
    S3_const = 100.0 * ((b_clip - 0.4) / (0.9 - 0.4))

    penalties = np.minimum(30.0, np.maximum(0.0, 100.0 * (raw["ann_vol"].fillna(0) - 0.20)))

    MomentumScore = 0.6*S1 + 0.2*S2 + 0.2*S3_const - penalties.values

    out = raw.copy()
    out["S1"] = S1
    out["S2"] = S2
    out["S3"] = S3_const
    out["penalty"] = penalties.values
    out["MomentumScore"] = MomentumScore
    out["enter_long"] = (out["MomentumScore"] >= 60) & (out["Z_mom"] >= 0.5) & (out["gate"] == 1)

    out = out[[
        "symbol","Z_mom","S1","S2","S3","penalty","MomentumScore","enter_long",
        "ann_vol","trend50>200","ts_mom_sign","r_12_1","r_6_1","r_3_1"
    ]]

    return out, breadth

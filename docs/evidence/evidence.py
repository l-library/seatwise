"""Evidence pipeline for the Seatwise design report.

Produces every number cited in chapter 0 of DESIGN.md:

  1. quality   — six-dimension data quality assessment for both datasets
  2. baseline  — forecast baselines (persistence / seasonal naive / profile) for
                 HKUST daily demand, floor share, and KTH 30-min zone utilisation
  3. calendar  — how much variance academic-calendar + holiday features explain
  4. drift     — regime shift evidence around 2019-11 .. 2022-05

Run:  .venv/bin/python evidence.py            (writes evidence.json + report.md)
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
HKUST_DIR = HERE / "dataverse-wifi"
KTH_PARQUET = HERE / "kth" / "kth_library_occupancy.parquet"

# clean window: calendar PDFs for 2013-14..2018-19 parse unambiguously.
# 2019-07 onwards is kept only as the anomaly / drift window (see section 4).
FIT_START, FIT_END = "2014-02-01", "2019-06-30"
DRIFT_START, DRIFT_END = "2019-07-01", "2022-05-31"
FLOORS = ["G", "1", "LG1", "LG3", "LG4"]
res: dict = {}


# ---------------------------------------------------------------- loaders
def load_hkust_daily() -> pd.DataFrame:
    frames = [pd.read_csv(f) for f in sorted(HKUST_DIR.glob("*-wifi-raw.csv"))]
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def load_hkust_period() -> pd.DataFrame:
    frames = [pd.read_csv(f) for f in sorted(HKUST_DIR.glob("*-wifi-period-raw.csv"))]
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def term_table() -> pd.DataFrame:
    """Verified from Registry calendar PDFs (see hkust_calendar_terms.json)."""
    rows = [
        ("2014-02-04", "2014-05-09", "2014-05-17", "2014-05-29", "spring"),
        ("2014-09-01", "2014-11-29", "2014-12-08", "2014-12-19", "fall"),
        ("2015-02-02", "2015-05-09", "2015-05-18", "2015-05-30", "spring"),
        ("2015-09-01", "2015-11-30", "2015-12-08", "2015-12-19", "fall"),
        ("2016-02-01", "2016-05-09", "2016-05-17", "2016-05-28", "spring"),
        ("2016-09-01", "2016-11-30", "2016-12-07", "2016-12-19", "fall"),
        ("2017-02-01", "2017-05-09", "2017-05-16", "2017-05-27", "spring"),
        ("2017-09-01", "2017-11-30", "2017-12-07", "2017-12-19", "fall"),
        ("2018-02-01", "2018-05-09", "2018-05-16", "2018-05-29", "spring"),
        ("2018-09-03", "2018-12-01", "2018-12-08", "2018-12-20", "fall"),
        ("2019-01-30", "2019-05-09", "2019-05-17", "2019-05-29", "spring"),
    ]
    cols = ["start", "classes_end", "exam_start", "exam_end", "term"]
    df = pd.DataFrame(rows, columns=cols)
    for c in cols[:-1]:
        df[c] = pd.to_datetime(df[c])
    return df


def phase_of(dates: pd.Series, tt: pd.DataFrame) -> pd.Series:
    """in_term / exam / break, from the academic calendar."""
    out = pd.Series("break", index=dates.index)
    for _, r in tt.iterrows():
        in_term = (dates >= r.start) & (dates <= r.classes_end)
        exam = (dates >= r.exam_start) & (dates <= r.exam_end)
        out[in_term] = "in_term"
        out[exam] = "exam"
    return out


# ---------------------------------------------------------------- 1. quality
def quality(hk_daily: pd.DataFrame, hk_period: pd.DataFrame, kth: pd.DataFrame) -> dict:
    q: dict = {}

    # --- HKUST completeness: which days / months are present
    days = pd.Series(sorted(hk_daily.Date.unique()))
    full = pd.date_range(days.min(), days.max(), freq="D")
    q["hkust_days_expected"] = len(full)
    q["hkust_days_present"] = len(days)
    q["hkust_day_coverage_pct"] = round(100 * len(days) / len(full), 2)
    q["hkust_months_present"] = int(days.dt.to_period("M").nunique())
    q["hkust_span"] = [str(days.min().date()), str(days.max().date())]

    # --- HKUST consistency: group sum vs Total, floor sum vs All-Floors
    tot = hk_daily[hk_daily["User-Group"] == "Total"]
    grp = hk_daily[hk_daily["User-Group"] != "Total"]
    gsum = grp.groupby(["Date", "Floor"])["User-Count"].sum()
    tval = tot.set_index(["Date", "Floor"])["User-Count"]
    j = pd.concat([gsum.rename("g"), tval.rename("t")], axis=1).dropna()
    q["hkust_group_sum_eq_total_pct"] = round(100 * (j.g == j.t).mean(), 2)
    q["hkust_group_sum_n"] = int(len(j))

    fsum = tot[tot.Floor != "All-Floors"].groupby("Date")["User-Count"].sum()
    aval = tot[tot.Floor == "All-Floors"].set_index("Date")["User-Count"]
    k = pd.concat([fsum.rename("f"), aval.rename("a")], axis=1).dropna()
    q["hkust_floor_sum_eq_all_pct"] = round(100 * (k.f == k.a).mean(), 2)
    q["hkust_floor_sum_median_gap"] = int((k.f - k.a).abs().median())
    q["hkust_floor_sum_median_ratio"] = round(float((k.f / k.a).median()), 2)

    # --- HKUST validity: zero-traffic days, device-per-user ratio
    q["hkust_zero_days"] = int((aval == 0).sum())
    q["hkust_zero_days_pct"] = round(100 * float((aval == 0).mean()), 2)
    conn = tot[tot.Floor != "All-Floors"]
    q["hkust_connections_per_user"] = round(
        float(conn["WiFi-Conn"].sum() / conn["User-Count"].sum()), 2
    )

    # --- HKUST timeliness: which slices exist
    q["hkust_hourly_months"] = ["2020-06"]
    q["hkust_periods"] = sorted(
        hk_period[hk_period.Period != "All-Periods"].Period.unique().tolist()
    )

    # --- KTH completeness / validity
    ts = pd.to_datetime(kth["time"])
    kth_per_day = ts.dt.date.value_counts()
    q["kth_rows"] = int(len(kth))
    q["kth_days"] = int(kth_per_day.size)
    q["kth_samples_per_day_median"] = int(kth_per_day.median())
    q["kth_samples_per_day_min"] = int(kth_per_day.min())
    q["kth_span"] = [str(ts.min()), str(ts.max())]
    q["kth_median_interval_s"] = int(ts.sort_values().diff().dt.total_seconds().median())
    zones = [c for c in kth.columns if c != "time"]
    q["kth_capped_rows_pct"] = {
        z: round(100 * float((kth[z] == 100).mean()), 2) for z in zones
    }
    q["kth_all_zero_days"] = int((kth.set_index(ts)[zones].sum(axis=1).resample("D").sum() == 0).sum())
    return q


# ---------------------------------------------------------------- 2. baselines
def mae(a, b) -> float:
    m = ~(np.isnan(a) | np.isnan(b))
    return float(np.mean(np.abs(a[m] - b[m])))


def baselines(hk_daily: pd.DataFrame, kth: pd.DataFrame) -> dict:
    b: dict = {}

    # ---- HKUST: daily building demand (All-Floors, Total)
    tot = hk_daily[(hk_daily["User-Group"] == "Total") & (hk_daily.Floor == "All-Floors")]
    s = tot.groupby("Date")["User-Count"].sum().asfreq("D")
    fit = s[(s.index >= FIT_START) & (s.index <= "2018-08-31")]
    profiles = {
        "weekly_mean": fit.groupby(fit.index.dayofweek).mean(),
        "weekly_median": fit.groupby(fit.index.dayofweek).median(),
    }

    def score_window(start: str, end: str, label: str) -> None:
        test = s[(s.index >= start) & (s.index <= end)]
        d = pd.DataFrame(index=test.index)
        d["y"] = test
        d["dow"] = d.index.dayofweek
        d["persist"] = s.shift(1).reindex(test.index)
        d["same_weekday_last_week"] = s.shift(7).reindex(test.index)
        d["weekly_mean"] = d.dow.map(profiles["weekly_mean"])
        d["weekly_median"] = d.dow.map(profiles["weekly_median"])
        # seasonal profile x recent level: dow shape from history, level from last 7 days
        shape = profiles["weekly_mean"] / profiles["weekly_mean"].mean()
        level = s.shift(1).rolling(7, min_periods=4).mean().reindex(test.index)
        d["profile_x_level"] = d.dow.map(shape) * level
        d = d.dropna(subset=["y"])
        b[f"hkust_daily_{label}"] = {
            "window": [start, end],
            "n": int(len(d)),
            "mean_y": int(d.y.mean()),
            "mae": {c: round(mae(d[c].values, d.y.values)) for c in
                    ["persist", "same_weekday_last_week", "weekly_mean", "weekly_median", "profile_x_level"]},
        }

    score_window("2018-09-01", "2019-06-30", "holdout_clean")
    score_window("2019-09-01", "2019-11-30", "holdout_disruption")
    b["hkust_period_share"] = (
        load_hkust_period()
        .query("`User-Group` == 'Total' and Period != 'All-Periods'")
        .groupby("Period")["User-Count"].sum()
        .pipe(lambda x: (x / x.sum()).round(3)).to_dict()
    )

    # ---- KTH: 30-min-ahead zone utilisation
    ts = pd.to_datetime(kth["time"])
    zones = [c for c in kth.columns if c != "time"]
    cap = {z: float(kth.groupby(ts.dt.date)[z].max().quantile(0.95)) for z in zones}
    kth = kth.assign(ts=ts.values)
    u = kth.melt(id_vars=["ts"], value_vars=zones, var_name="zone", value_name="occ")
    u = u.sort_values(["zone", "ts"]).reset_index(drop=True)
    u["util"] = (u.occ / u.zone.map(cap)).clip(0, 1)
    u["dow"] = u.ts.dt.dayofweek
    u["hour"] = u.ts.dt.hour
    u["minute"] = u.ts.dt.minute
    step = 10  # ~10 samples * 3 min = 30 min
    u["y"] = u.groupby("zone")["util"].shift(-step)
    u["persist"] = u.util
    u["seasonal"] = u.groupby(["zone", "dow", "hour"])["util"].transform("median")
    u["profile_x_level"] = u["seasonal"] * (
        u.groupby("zone")["util"].transform(lambda x: x.rolling(20, min_periods=5).mean())
        / u.groupby("zone")["seasonal"].transform(lambda x: x.rolling(20, min_periods=5).mean())
    )
    m = u.dropna(subset=["y", "seasonal"])
    b["kth_30min"] = {
        "n": int(len(m)),
        "capacity_proxy": {k: round(v) for k, v in cap.items()},
        "mae": {
            "persistence": round(mae(m.persist.values, m.y.values), 4),
            "seasonal_naive": round(mae(m.seasonal.values, m.y.values), 4),
            "profile_times_recent_level": round(
                mae(np.clip(m.profile_x_level.fillna(m.seasonal).values, 0, 1), m.y.values), 4
            ),
        },
    }

    # calibration + guidance value: "will this zone still have a free seat in 30 min?"
    # event rate is set near 10% so the calibration check is not degenerate.
    m2 = m.copy()
    thr = float(m2.y.quantile(0.90))
    m2["event"] = m2.y >= thr
    m2["bin"] = pd.cut(m2.seasonal, np.linspace(0, m2.seasonal.max(), 6), include_lowest=True)
    cal = m2.groupby("bin").agg(pred=("seasonal", "mean"), actual=("event", "mean"), n=("event", "size"))
    b["kth_calibration"] = {
        "threshold_util": round(thr, 3),
        "base_rate": round(float(m2.event.mean()), 3),
        "bins": {str(i): [round(r.pred, 3), round(r.actual, 3), int(r.n)] for i, r in cal.iterrows()},
    }

    # guidance value: at each weekday 8-20 timestamp, one arrival picks a zone.
    # old style: pick the zone they prefer (uniform over zones).
    # new style: pick the zone with the lowest predicted utilisation (seasonal profile).
    tsx = pd.to_datetime(kth["time"])
    week = kth[(tsx.dt.dayofweek < 5) & tsx.dt.hour.between(8, 20)].copy()
    week["ts"] = tsx[week.index]
    free = pd.DataFrame({z: (cap[z] - week[z]).clip(lower=0) for z in zones})

    prof = week.assign(dow=week.ts.dt.dayofweek, hour=week.ts.dt.hour).groupby(["dow", "hour"])[zones].median()
    score = pd.DataFrame(
        [prof.loc[(d, h)].values for d, h in zip(week.ts.dt.dayofweek, week.ts.dt.hour)],
        index=week.index, columns=zones,
    )
    best = score.values.argmin(axis=1)
    old_ok = np.array([free.iloc[i][zones[j]] >= 1 for i, j in enumerate(np.arange(len(week)) % len(zones))])
    new_ok = np.array([free.iloc[i][zones[j]] >= 1 for i, j in enumerate(best)])
    b["kth_guidance"] = {
        "n_arrivals": int(len(week)),
        "find_seat_fail_pct_old": round(100 * float(1 - old_ok.mean()), 2),
        "find_seat_fail_pct_new": round(100 * float(1 - new_ok.mean()), 2),
        "relative_reduction_pct": round(
            100 * float((1 - new_ok.mean()) / max(1e-9, 1 - old_ok.mean()) - 1), 1
        ),
    }
    return b


# ---------------------------------------------------------------- 3. calendar effects
def calendar_effects(hk_daily: pd.DataFrame) -> dict:
    import holidays

    tot = hk_daily[(hk_daily["User-Group"] == "Total") & (hk_daily.Floor == "All-Floors")]
    s = tot.groupby("Date")["User-Count"].sum().asfreq("D")
    s = s[(s.index >= FIT_START) & (s.index <= FIT_END)]
    tt = term_table()
    hk = holidays.HK(years=range(2014, 2023))

    X = pd.DataFrame(index=s.index)
    X["dow"] = s.index.dayofweek
    X["is_weekend"] = (X.dow >= 5).astype(int)
    X["phase"] = phase_of(pd.Series(s.index, index=s.index), tt)
    X["holiday"] = [1 if d.date() in hk else 0 for d in s.index]
    X["week_of_term"] = [
        _week_of_term(d, tt) for d in s.index
    ]

    y_all = np.log1p(s.values)
    keep = ~np.isnan(y_all)
    X, y = X[keep], y_all[keep]

    def r2(cols: list[str]) -> float:
        M = pd.concat([pd.get_dummies(X[cols], drop_first=True, dtype=float)], axis=1)
        M.insert(0, "const", 1.0)
        beta, *_ = np.linalg.lstsq(M.values, y, rcond=None)
        pred = M.values @ beta
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        return round(1 - ss_res / ss_tot, 3)

    out = {
        "window": [str(s.index.min().date()), str(s.index.max().date())],
        "n": int(len(s)),
        "r2_dow_only": r2(["dow"]),
        "r2_dow_weekend_holiday": r2(["dow", "is_weekend", "holiday"]),
        "r2_plus_term_phase": r2(["dow", "is_weekend", "holiday", "phase"]),
        "r2_plus_week_of_term": r2(["dow", "is_weekend", "holiday", "phase", "week_of_term"]),
    }
    ph = X.groupby("phase").size().to_dict()
    out["phase_days"] = {k: int(v) for k, v in ph.items()}
    med = s.groupby(X.phase).median().round(0).to_dict()
    out["median_by_phase"] = {k: float(v) for k, v in med.items()}
    return out


def _week_of_term(d: pd.Timestamp, tt: pd.DataFrame) -> int:
    for _, r in tt.iterrows():
        if r.start <= d <= r.exam_end:
            return int(min(20, (d - r.start).days // 7) + 1)
    return 0


# ---------------------------------------------------------------- 4. drift
def drift(hk_daily: pd.DataFrame) -> dict:
    tot = hk_daily[(hk_daily["User-Group"] == "Total") & (hk_daily.Floor == "All-Floors")]
    s = tot.groupby("Date")["User-Count"].sum().asfreq("D")
    pre = s[(s.index >= "2016-09-01") & (s.index <= "2019-06-30")]
    by_year = s.groupby(s.index.year).agg(["count", "mean", "median"]).round(0)
    # floor mix shift before vs after
    fl = hk_daily[(hk_daily["User-Group"] == "Total") & (hk_daily.Floor.isin(FLOORS))]
    pre_mix = fl[(fl.Date >= "2016-09-01") & (fl.Date <= "2019-06-30")].groupby("Floor")["User-Count"].sum()
    post_mix = fl[(fl.Date >= "2021-09-01") & (fl.Date <= "2022-05-31")].groupby("Floor")["User-Count"].sum()
    return {
        "year_mean_median": by_year.to_dict(),
        "pre_median": float(pre.median()),
        "floor_mix_2016_2019": (pre_mix / pre_mix.sum()).round(3).to_dict(),
        "floor_mix_2021_2022": (post_mix / post_mix.sum()).round(3).to_dict(),
        "drift_window": [DRIFT_START, DRIFT_END],
    }


# ---------------------------------------------------------------- 5. scarcity
def scarcity(hk_daily: pd.DataFrame, kth: pd.DataFrame) -> dict:
    tot = hk_daily[(hk_daily["User-Group"] == "Total") & (hk_daily.Floor.isin(FLOORS))]
    fit = tot[(tot.Date >= FIT_START) & (tot.Date <= FIT_END)]
    per_floor_day = fit.groupby(["Date", "Floor"])["User-Count"].sum().unstack()
    share = per_floor_day.div(per_floor_day.sum(axis=1), axis=0)
    busy = fit[fit.Date.dt.dayofweek < 5].groupby("Floor")["User-Count"].mean()
    ts = pd.to_datetime(kth["time"])
    zones = [c for c in kth.columns if c != "time"]
    cap = {z: float(kth.groupby(ts.dt.date)[z].max().quantile(0.95)) for z in zones}
    wk = kth[(ts.dt.dayofweek < 5) & ts.dt.hour.between(8, 20)]
    full_rate = {z: round(100 * float((wk[z] >= 0.99 * cap[z]).mean()), 1) for z in zones}
    return {
        "hkust_floor_mean_daily": busy.round(0).to_dict(),
        "hkust_floor_imbalance_ratio": round(float(busy.max() / busy.min()), 1),
        "hkust_floor_share_median": share.median().round(3).to_dict(),
        "hkust_floor_share_iqr": (share.quantile(.75) - share.quantile(.25)).round(3).to_dict(),
        "kth_weekday_full_pct": full_rate,
        "kth_weekday_mean_util": round(float(np.mean([
            float(((wk[z] / cap[z]).clip(0, 1)).mean()) for z in zones])), 3),
    }


# ---------------------------------------------------------------- report
def main() -> None:
    hk_daily = load_hkust_daily()
    hk_period = load_hkust_period()
    kth = pd.read_parquet(KTH_PARQUET)

    res["quality"] = quality(hk_daily, hk_period, kth)
    res["baselines"] = baselines(hk_daily, kth)
    res["calendar"] = calendar_effects(hk_daily)
    res["drift"] = drift(hk_daily)
    res["scarcity"] = scarcity(hk_daily, kth)

    (HERE / "evidence.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

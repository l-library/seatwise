"""Render the evidence figures used in assignment 2 (chapter 0 / 6 / 7).

Reads evidence.json produced by evidence.py, writes PNGs to ../fig/.
Run: .venv/bin/python make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
OUT = HERE.parent / "fig"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUTED, ACCENT, GRID = "#1F2A40", "#6B7690", "#2F6FBF", "#E3E7EE"
plt.rcParams.update({
    "font.family": ["DengXian", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
})

ev = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))


def bar_mae() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.0))
    hk = ev["baselines"]["hkust_daily_holdout_clean"]["mae"]
    labels = ["persistence\n(昨日)", "同日上周", "weekly mean", "weekly median",
              "季节形状 ×\n近期水平"]
    keys = ["persist", "same_weekday_last_week", "weekly_mean", "weekly_median", "profile_x_level"]
    vals = [hk[k] for k in keys]
    colors = [MUTED, MUTED, MUTED, MUTED, ACCENT]
    axes[0].bar(range(len(vals)), vals, color=colors, width=0.62)
    axes[0].set_xticks(range(len(vals)))
    axes[0].set_xticklabels(labels, fontsize=7, rotation=22, ha="right")
    axes[0].set_ylim(0, max(vals) * 1.16)
    axes[0].set_ylabel("MAE（人次/日）")
    axes[0].set_title("日粒度需求（HKUST，留出集 2018-09 到 2019-06）", fontsize=10.6)
    for i, v in enumerate(vals):
        axes[0].text(i, v + 30, str(v), ha="center", fontsize=10.6,
                     color=ACCENT if i == 4 else MUTED)

    kt = ev["baselines"]["kth_30min"]["mae"]
    keys2 = ["persistence", "seasonal_naive", "profile_times_recent_level"]
    labels2 = ["persistence", "季节朴素\n(zone,dow,hour)", "季节形状 ×\n近期水平"]
    vals2 = [kt[k] for k in keys2]
    axes[1].bar(range(len(vals2)), vals2, color=[MUTED, MUTED, ACCENT], width=0.55)
    axes[1].set_xticks(range(len(vals2)))
    axes[1].set_xticklabels(labels2, fontsize=7, rotation=22, ha="right")
    axes[1].set_ylim(0, max(vals2) * 1.16)
    axes[1].set_ylabel("MAE（利用率）")
    axes[1].set_title("30 分钟前瞻占用（KTH，区域利用率）", fontsize=10.6)
    for i, v in enumerate(vals2):
        axes[1].text(i, v + 0.002, f"{v:.3f}", ha="center", fontsize=10.6,
                     color=ACCENT if i == 2 else MUTED)
    fig.suptitle("图 A-1  基线模型对照：日粒度需求与 30 分钟前瞻占用", fontsize=11, y=1.06)
    fig.savefig(OUT / "figA1_baseline_mae.png")
    plt.close(fig)


def calendar_r2() -> None:
    c = ev["calendar"]
    steps = ["星期", "+ 假期", "+ 学期/考试期", "+ 学期第几周"]
    vals = [c["r2_dow_only"], c["r2_dow_weekend_holiday"],
            c["r2_plus_term_phase"], c["r2_plus_week_of_term"]]
    fig, ax = plt.subplots(figsize=(5.0, 2.8))
    bars = ax.bar(steps, vals, color=[MUTED, MUTED, ACCENT, ACCENT], width=0.55)
    ax.set_ylim(0, 0.6)
    ax.set_ylabel("解释力 R²（log 人次）")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.2f}", ha="center", fontsize=9.6)
    ax.set_title("图 A-2  校历特征对日到馆人次的解释力（2014-02 到 2019-06，n=1,974）", fontsize=10.6)
    fig.savefig(OUT / "figA2_calendar_r2.png")
    plt.close(fig)


def imbalance() -> None:
    s = ev["scarcity"]
    floors = ["LG1", "LG4", "G", "LG3", "1"]
    means = [s["hkust_floor_mean_daily"][f] for f in floors]
    shares = [s["hkust_floor_share_median"][f] * 100 for f in floors]
    iqr = [s["hkust_floor_share_iqr"][f] * 100 for f in floors]

    fig, axes = plt.subplots(1, 2, figsize=(8.0, 2.8))
    axes[0].barh(floors, means, color=[ACCENT, MUTED, MUTED, MUTED, MUTED], height=0.6)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("工作日日均到馆人次")
    axes[0].set_title("工作日日均到馆人次", fontsize=10.6)
    for i, v in enumerate(means):
        axes[0].text(v + 30, i, f"{v:.0f}", va="center", fontsize=10.6)

    axes[1].barh(floors, shares, xerr=iqr, color=MUTED, height=0.6,
                 error_kw={"ecolor": INK, "lw": 0.9, "capsize": 3})
    axes[1].invert_yaxis()
    axes[1].set_xlabel("份额（中位数 ± 四分位间距，%）")
    axes[1].set_title("需求份额", fontsize=10.6)
    fig.suptitle("图 A-3  楼层到馆人次与需求份额（HKUST，2014-02 到 2019-06）", fontsize=11, y=1.05)
    fig.savefig(OUT / "figA3_floor_imbalance.png")
    plt.close(fig)


def drift() -> None:
    d = ev["drift"]["year_mean_median"]
    years = [int(y) for y in d["mean"]]
    mean = [d["mean"][str(y)] for y in years]
    median = [d["median"][str(y)] for y in years]
    fig, ax = plt.subplots(figsize=(5.6, 2.8))
    ax.plot(years, mean, marker="o", color=MUTED, label="年均值")
    ax.plot(years, median, marker="o", color=ACCENT, label="年中位数")
    ax.axvspan(2019.5, 2022.4, color="#FFF2D9", zorder=0)
    ax.text(2020.9, max(mean) * 0.96, "异常 / 恢复期\n（不进入拟合）", ha="center", fontsize=10.6, color="#8A6A1F")
    ax.set_ylabel("日人次")
    ax.set_xlabel("年")
    ax.legend(frameon=False, fontsize=10.6, loc="lower right")
    ax.set_title("图 A-4  年日均到馆人次（2014 到 2022）", fontsize=10.6)
    fig.savefig(OUT / "figA4_drift.png")
    plt.close(fig)


def period_profile() -> None:
    p = ev["baselines"]["hkust_period_share"]
    order = ["Early-Morning", "Morning", "Afternoon", "Late-Afternoon", "Evening", "Midnight"]
    names = ["清晨", "上午", "午后", "傍晚前", "晚间", "深夜"]
    vals = [p[k] * 100 for k in order]
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    ax.bar(names, vals, color=[MUTED, MUTED, ACCENT, ACCENT, MUTED, MUTED], width=0.6)
    ax.set_ylabel("需求占比 %")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.6, f"{v:.1f}", ha="center", fontsize=10.6)
    ax.set_title("图 A-5  日内时段需求份额", fontsize=10.6)
    fig.savefig(OUT / "figA5_period_profile.png")
    plt.close(fig)


if __name__ == "__main__":
    bar_mae()
    calendar_r2()
    imbalance()
    drift()
    period_profile()
    print("\n".join(str(p) for p in sorted(OUT.glob("*.png"))))

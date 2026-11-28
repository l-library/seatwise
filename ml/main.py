"""Seatwise 离线脚本入口。

第一周只需要 `--task quality|train|backtest` 三个子命令存在且可运行；
三个任务的实际内容分别在第三周落地（数据质量闸门、B1–B3 训练、回测）。
"""

import argparse
from collections.abc import Callable

Task = Callable[[], int]


def quality() -> int:
    print("quality: 数据质量六维闸门尚未实现（第三周）")
    return 0


def train() -> int:
    print("train: B1–B3 训练尚未实现（第三周）")
    return 0


def backtest() -> int:
    print("backtest: 固定时间切分回测尚未实现（第三周）")
    return 0


TASKS: dict[str, Task] = {
    "quality": quality,
    "train": train,
    "backtest": backtest,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="main.py", description="Seatwise 离线训练与数据脚本")
    parser.add_argument("--task", required=True, choices=sorted(TASKS), help="要执行的任务")
    args = parser.parse_args(argv)
    return TASKS[args.task]()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""把 Apifox 重导出的 openapi.yaml 归一化成仓库需要的形态。

为什么存在：Apifox 导出有两处修不掉的缺陷——
1. 可空枚举只能导出 `$ref` 与 `nullable: true` 同层并列，而 openapi-typescript
   会忽略 `$ref` 旁的 `nullable`，丢掉 `| null`。只有 `allOf: [$ref]` +
   `nullable: true` 才能生成 `SettleReason | null`；这种形态 Apifox 侧无法产出。
2. `servers` 恒导出为 `servers: []`，MCP 的项目设置改不动它；仓库需要
   `servers: [{url: /api/v1, description: 统一接口前缀（docs/API.md 1.1）}]`。

因此从 Apifox 重导出后应先跑本脚本再 `pnpm gen:api`。

docs/openapi.yaml 是逐字校对过的文件，故本脚本做纯文本级的外科式替换
（不用 PyYAML 加载再 dump，那会重排 key、产生整文件 diff），且变换幂等：
改写后 `$ref` 缩进比 `nullable` 深一层，二次运行不会再次命中。

用法：
    python3 scripts/normalize-openapi.py                # 就地处理 docs/openapi.yaml
    python3 scripts/normalize-openapi.py --path 其他.yaml
    python3 scripts/normalize-openapi.py --dry-run     # 只报告不落盘
    python3 scripts/normalize-openapi.py --self-check  # 内置用例自检
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_PATH = "docs/openapi.yaml"

# `$ref` 行不以 `- ` 开头：列表项形如 `- $ref:`，已处于 allOf 内部，不该被再包一层。
REF_LINE = re.compile(r"^(\s+)\$ref:(\s*\S.*)$")
NULLABLE_TRUE_LINE = re.compile(r"^(\s+)nullable:\s*true\s*$")
SERVERS_EMPTY_LINE = re.compile(r"^(\s*)servers:\s*\[\]\s*$")
SERVERS_NONEMPTY_LINE = re.compile(r"^(\s*)servers:\s*(\S.*)?$")

SERVERS_BLOCK = ["  - url: /api/v1", "    description: 统一接口前缀（docs/API.md 1.1）"]


def transform(lines: list[str]) -> tuple[list[str], int, str]:
    """返回 (新行列表, 可空引用改写计数, servers 状态)。"""
    out: list[str] = []
    ref_count = 0
    servers_status = "不存在"
    i = 0
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1] if i + 1 < len(lines) else ""

        ref_match = REF_LINE.match(line)
        nullable_match = NULLABLE_TRUE_LINE.match(next_line)
        if ref_match and nullable_match and ref_match.group(1) == nullable_match.group(1):
            indent = ref_match.group(1)
            out.append(f"{indent}allOf:\n")
            out.append(f"{indent}  - {line[len(indent):].rstrip()}\n")
            out.append(next_line)
            ref_count += 1
            i += 2
            continue

        empty_match = SERVERS_EMPTY_LINE.match(line)
        if empty_match:
            indent = empty_match.group(1)
            out.append(f"{indent}servers:\n")
            for block_line in SERVERS_BLOCK:
                out.append(f"{indent}{block_line}\n")
            servers_status = "已改写"
            i += 1
            continue

        # 非空 servers 块（openapi-typescript 产物依赖它）保持原样。
        if SERVERS_NONEMPTY_LINE.match(line) and not empty_match:
            servers_status = "已存在，跳过"

        out.append(line)
        i += 1
    return out, ref_count, servers_status


def split_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def normalize(text: str) -> tuple[str, int, str, bool]:
    lines = split_lines(text)
    new_lines, ref_count, servers_status = transform(lines)
    changed = new_lines != lines
    if not changed:
        # 保字节：无改动时原样返回，避免行尾差异。
        return text, ref_count, servers_status, False
    joined = "".join(new_lines)
    if text.endswith("\n") and not joined.endswith("\n"):
        joined += "\n"
    return joined, ref_count, servers_status, True


def process(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new_text, ref_count, servers_status, changed = normalize(text)
    if not changed:
        print("无需改动")
        return 0
    if not dry_run:
        path.write_text(new_text, encoding="utf-8", newline="")
    print(f"$ref+nullable: {ref_count} 处改写 | servers: {servers_status}")
    return 0


def assert_equal(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        print(f"self-check 失败：{label}")
        print("--- 实际 ---")
        print(actual)
        print("--- 期望 ---")
        print(expected)
        raise AssertionError(label)


def self_check() -> int:
    # 用例 1：Apifox 形态的可空引用 → allOf 形态，逐字符相等，且再跑为 no-op。
    case1_input = (
        "    Settle:\n"
        "      properties:\n"
        "        reason:\n"
        "          $ref: '#/components/schemas/SettleReason'\n"
        "          nullable: true\n"
    )
    case1_expected = (
        "    Settle:\n"
        "      properties:\n"
        "        reason:\n"
        "          allOf:\n"
        "            - $ref: '#/components/schemas/SettleReason'\n"
        "          nullable: true\n"
    )
    once, count, _, changed = normalize(case1_input)
    assert_equal(once, case1_expected, "用例 1 首次变换")
    if not changed or count != 1:
        raise AssertionError("用例 1 应报告恰好 1 处改写")
    twice, count2, _, changed2 = normalize(once)
    if changed2 or count2 != 0 or twice != once:
        raise AssertionError("用例 1 二次运行应为 no-op")

    # 用例 2a：已是 allOf 形态 → no-op（含列表项 `- $ref:` 不被误包一层）。
    case2, count2a, _, changed2a = normalize(case1_expected)
    if changed2a or count2a != 0 or case2 != case1_expected:
        raise AssertionError("用例 2a 已是 allOf 形态应无改动")

    # 用例 2b：servers: [] → 三行 servers 块。
    case2b_input = "openapi: 3.0.3\nservers: []\ninfo:\n  title: t\n"
    case2b_expected = (
        "openapi: 3.0.3\n"
        "servers:\n"
        "  - url: /api/v1\n"
        "    description: 统一接口前缀（docs/API.md 1.1）\n"
        "info:\n"
        "  title: t\n"
    )
    got, _, servers_status, changed2b = normalize(case2b_input)
    assert_equal(got, case2b_expected, "用例 2b servers 改写")
    if not changed2b or servers_status != "已改写":
        raise AssertionError("用例 2b 应报告 servers 已改写")

    # 用例 2c：nullable: false 不受影响。
    case2c_input = (
        "        reason:\n"
        "          $ref: '#/components/schemas/SettleReason'\n"
        "          nullable: false\n"
    )
    got2c, count2c, _, changed2c = normalize(case2c_input)
    if changed2c or count2c != 0 or got2c != case2c_input:
        raise AssertionError("用例 2c nullable: false 应保持原样")

    print("self-check 通过：4 个用例（含幂等）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="归一化 Apifox 重导出的 openapi.yaml")
    parser.add_argument("--path", default=DEFAULT_PATH, help=f"目标 YAML 文件（默认 {DEFAULT_PATH}）")
    parser.add_argument("--dry-run", action="store_true", help="只报告改动，不写回文件")
    parser.add_argument("--self-check", action="store_true", help="跑内置用例自检后退出")
    args = parser.parse_args(argv)
    if args.self_check:
        return self_check()
    return process(Path(args.path), args.dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"self-check 失败：{exc}", file=sys.stderr)
        sys.exit(1)

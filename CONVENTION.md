# Seatwise 开发约定

面向全体成员与 AI agent 的工程约定。产品背景与功能规划见 [README.md](README.md)；英文版（供 agent 使用）见 [AGENTS.md](AGENTS.md)。

## 1. 项目总体结构

```
seatwise/
├── .agents/    项目级 agent skills，入库并由全体成员共享
├── backend/    Spring Boot 后端（Java 25，Maven Wrapper，包根 com.seatwise）
│   ├── src/main/java/com/seatwise/...   后端源码
│   ├── src/main/resources/              配置（application.yaml）
│   └── src/test/java/...                测试（JUnit 5，目录结构与源码一一对应）
├── frontend/   React 前端（React 19 + TypeScript 6 + Vite 8，包管理 pnpm）
│   └── src/                             页面、组件、接口调用
└── ml/         占用预测模型与数据脚本（Python 3.14，uv + pyproject）
```

分层约定：

- backend 按 `controller → service → repository` 分层，跨层直接调用，不绕层。
- frontend 按功能组织组件与页面，接口调用集中管理，组件文件名 PascalCase。
- ml 存放离线训练与数据脚本，不进入运行时链路；可复用的预测能力经 backend 接口暴露。
- `.agents/` 永远不进 `.gitignore`：它是仓库的一部分，也是成员协作的一部分，所有人与 agent 共用。
- 接口契约放 OpenAPI 文档（Apifox 维护），契约先行：先改契约，再改实现。
- 部署用 Docker Compose（规划中），配置文件放在仓库根目录。

## 2. 开发环境

前置：JDK 25、Node.js ≥ 24 + pnpm、Python 3.14 + uv、MySQL 8（数据库尚未接入时可不启动）。

### frontend

```bash
pnpm install        # 安装依赖（用 pnpm，不要混用 npm/yarn）
pnpm dev            # 本地开发
pnpm build          # 类型检查 + 构建（tsc -b && vite build）
pnpm lint           # oxlint
pnpm preview        # 预览构建产物
```

测试暂无脚手架；引入时统一用 vitest，并在 `package.json` 增加 `test` script。

### backend

```bash
./mvnw spring-boot:run   # 本地开发（Windows 用 mvnw.cmd）
./mvnw test              # JUnit 5 测试
./mvnw package           # 打包
```

### ml

```bash
uv sync             # 按 pyproject 建立/更新虚拟环境
uv run main.py      # 运行脚本
```

测试统一用 pytest，引入时加为 dev dependency。

### 提交前自检

改动涉及哪个模块，就跑哪个模块的 lint + build + test；命令与结果写进 PR 的「验证」一节。全绿才算完成。

## 3. Git 协作规范

### 3.1 分支模型（只有 main 和 feat 分支）

- `main`：唯一长期分支，永远保持可构建、可发布。禁止直接 push，一切改动经 PR 合入。
- `feat/<slug>`：从 `main` 切出的短期分支，如 `feat/booking-state-machine`、`feat/12-credit-rules`（带 issue 号）。修 bug 也用 `feat/` 分支，type 体现在 commit 里。
- 流程：`main` 切出 `feat/x` → 开发 + 自测 → PR 回 `main` → review → squash merge → 删除 `feat/x`。
- 分支生命周期尽量短（几天内合并），一个 PR 只做一件事；落后 `main` 时用 `git rebase main` 同步，不产生多余 merge commit。
- 合并后删除分支；长期不合并的分支定期清理。

### 3.2 Commit 信息（Conventional Commits）

```
<type>(<scope>): <subject>

[body]

[footer]
```

- `type`：`feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`。
- `scope`：`backend` `frontend` `ml` `docs` `ci`，可省略。
- `subject`：英文祈使句，小写开头，不加句号，不超过 50 字符（如 `feat(backend): add seat hold transaction`）。
- `body`：说明「为什么」而不是「改了什么」，可中文，按需省略。
- `footer`：`Refs #12` 关联 issue，`Closes #12` 关闭 issue。
- 破坏性变更：type 后加 `!`，并在 footer 写 `BREAKING CHANGE: <说明>`。
- 一个 commit 只做一件事；不要把格式化、重命名和功能改动混在一个 commit 里。

### 3.3 Issue

标题格式：`<type>: <简述>`，如 `bug: 高峰期并发预约未拦截`、`feat: 对话订座工具调用`。

- Bug 报告：环境与版本 / 复现步骤 / 期望结果 / 实际结果 / 日志或截图。
- Feature：动机 / 方案概述 / 验收标准 / 边界（明确不做什么）。
- 新功能、跨模块改动、行为变更：先开 issue 讨论再动手。
- 新增项目级 skill（`.agents/` 下）：先开 issue 讨论，达成一致后再落地。

### 3.4 PR

- 标题就是一条 Conventional Commit（squash merge 后成为 `main` 上的 commit 信息）。
- 描述模板：

  ```markdown
  ## 变更内容
  ## 动机与关联（Refs #x）
  ## 验证（列出跑过的命令与结果）
  ## 检查清单
  ```

- 检查清单：

  ```markdown
  - [ ] lint / build / test 通过
  - [ ] OpenAPI 契约已同步更新
  - [ ] 无密钥、token、个人配置入库
  - [ ] 文本文件 UTF-8 + LF
  - [ ] 无无关改动（重构、格式化混入）
  ```

- 至少一人 review 通过后合并；合并方式 squash merge，合并后删除 feat 分支。

## 4. 编码格式

- 所有文本文件统一 **UTF-8（无 BOM）+ LF**。唯一例外：`*.bat` / `*.cmd` 用 CRLF。
- 缩进用空格，宽度由 [.editorconfig](.editorconfig) 规定：Java/Python/XML 4 空格，TS/JS/CSS/HTML/YAML 2 空格。
- 文件末尾保留一个空行；去掉行尾空白（Markdown 除外）。
- [.editorconfig](.editorconfig) 与 [.gitattributes](.gitattributes) 是机器强制的规则：IDE 请开启 EditorConfig 支持；提交前可用 `git diff --check` 检查空白与换行问题。
- 不要在同一个 commit 里做全文件格式化。

## 5. 一般编码须知

### 动手前

- 不臆测：先读文件与调用方，弄清受影响的流程再改；不假设代码行为。
- 只做被要求的事：不顺手重构、不改无关格式、不做无关修复。范围之外的问题记录下来另行处理。

### 实现

- 决策阶梯，停在第一个能解决问题的选项：这个东西需要存在吗 → 复用仓库里已有实现 → 用标准库 → 用平台原生能力 → 用已安装依赖 → 一行能写清就写一行 → 否则写最小可运行实现。
- 优先删除而不是新增。用最少的文件、最小的 diff。
- 写无聊的代码，不写聪明的代码。避免多余抽象、单实现接口、投机性配置、为未来预留的脚手架。
- 修根因，不修症状；改共享行为前先看所有调用方，能修公共路径就修公共路径。
- 注释写「为什么」，不写「做了什么」；能靠命名说清的不写注释。

### 不可妥协

- 边界输入校验、防数据丢失的错误处理、安全控制、可访问性、关键边界 case 的正确性——任何简化都不能牺牲这些。
- 密钥、token、个人配置不入库，用 `.env`（已在 `.gitignore`）。
- 非平凡的新逻辑必须留一个最小可运行检查（测试或脚本）；琐碎改动不必补测试。
- 测试的目录结构与命名镜像被测代码；测试里写具体输入输出，不写抽象桩数据。

### 项目特定

- 契约先行：改 REST 接口先改 OpenAPI 文档，再改实现，两侧在同一 PR 内同步。
- 并发正确性：预约状态变更走数据库事务 + 行锁，释放操作幂等，超时与宽限期可配置。
- LLM 只做查询与提议；订座、扣信用等后果性操作必须经用户确认；核心流程在没有 LLM 时也要可用。
- 隐私：预约数据不出域，对话中不泄露他人预约信息。

### 完成标准

需求的每一项都被实际验证过（跑过命令、看过输出），而不是「应该没问题」；lint / build / test 结果写进 PR。

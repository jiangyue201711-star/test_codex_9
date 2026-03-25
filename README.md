# MESIS-Bench eval.scm Batch Generator

该仓库提供一个批量任务生成器，用于生成符合 PRD 的 `eval.scm` 元循环解释器任务及测试集。

## 使用方式

```bash
python3 generate_mesis_bench.py --output-dir tasks --count 12 --seed 20260325
```

## 输出结构

```text
tasks/
  manifest.json
  task_0001_eval.scm
  task_0001_tests.json
  ...
```

## 关键特性

- **按 TaskSpec 动态生成** `eval.scm`：依据任务类型自动启用算术、变量、函数、递归、条件分支、多层/自宿主解析模块。
- 扩展任务类型：新增并强化 **J/K/L/M/N**（符号列表、局部作用域、惰性求值、标准输入输出、元程序任务），提升挑战性。
- 所有 `eval.scm` 均支持从标准输入读取任务文本，并支持程序运行阶段的基础 I/O（`read` / `read-line` / `display` / `write`）。
- 元循环解释器（Meta-Circular）
- 多层输入执行（`scheme ...` / `eval.scm ...` 链式头部）
- 3–5 条 deterministic 测试样例（按任务类型优先采样）
- `manifest.json` 与每个 task 的 `feature_flags` 用于快速筛选能力覆盖

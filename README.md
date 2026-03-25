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

- **每个任务都内置完整元循环解释器核心能力**：算术、变量、函数、闭包、递归、条件、局部作用域。 
- **按 TaskSpec 动态增强扩展能力**：J/K/L/M/N（符号列表、惰性求值、标准输入输出、元程序等）。
- 所有 `eval.scm` 均支持从标准输入读取任务文本，并支持程序运行阶段的基础 I/O（`read` / `read-line` / `display` / `write`）。
- 所有 `eval.scm` 均支持多层输入头（`scheme ...` / `eval.scm ...`）和运行期输入转发。
- 3–5 条 deterministic 测试样例（按任务类型优先采样）
- `manifest.json` 与每个 task 的 `feature_flags` 用于快速筛选能力覆盖

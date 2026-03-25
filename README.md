# MESIS-Bench eval.scm Batch Generator

该仓库提供一个批量任务生成器，用于生成符合 PRD 的 `eval.scm` 元循环解释器任务及测试集。

## 使用方式

```bash
python3 generate_mesis_bench.py --output-dir tasks --count 12 --seed 20260325
```

## 关键特性

- 每个任务都内置元循环解释器核心能力（闭包、递归、条件、局部作用域、多层输入解析）。
- 支持同一 `TASK_TYPES` 下的能力集合变化（如 A: `basic` vs `modulo`）。
- 新增语法与任务类型：
  - **O**：循环控制（`for` / `while`）
  - **P**：数组（`vector` / `vector-ref` / `vector-set!`）
  - **Q**：结构体/记录（基于 `hash`）
- 所有 `eval.scm` 支持标准输入读取与运行期输入转发，支持 `read/read-line/display/write`。
- 输出 `variants` + `feature_flags`，便于同类任务差异化评测。

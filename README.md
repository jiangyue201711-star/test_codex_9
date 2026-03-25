# MESIS-Bench eval.scm Batch Generator

该仓库提供一个批量任务生成器，用于生成符合 PRD 的 `eval.scm` 元循环解释器任务及测试集。

## 使用方式

```bash
python3 generate_mesis_bench.py --output-dir tasks --count 12 --seed 20260325
```

## 关键特性

- 每个任务都内置完整元循环解释器核心能力（闭包、递归、条件、局部作用域、多层输入解析）。
- 支持同一 `TASK_TYPES` 下的**能力集合变化**（例如 A 类型可生成 `basic` 算术集合或 `modulo` 扩展集合）。
- 输出 `variants` 字段，用于记录同类任务的能力差异配置。
- 所有 `eval.scm` 支持标准输入读取与运行期输入转发，支持 `read/read-line/display/write`。
- 3–5 条 deterministic 测试样例，按任务类型优先抽样。

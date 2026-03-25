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

## 覆盖能力

- 元循环解释器（Meta-Circular）
- 多层输入执行（`scheme ...` / `eval.scm ...` 链式头部）
- 算术、变量、函数、闭包、递归、条件分支
- 确定性测试样例（固定输入 -> 固定输出）

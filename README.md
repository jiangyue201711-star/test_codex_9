# MESIS-Bench eval.scm Batch Generator

该仓库提供一个批量任务生成器，用于生成符合 PRD 的 `eval.scm` 元循环解释器任务及测试集。

## 使用方式

```bash
python3 generate_mesis_bench.py --output-dir tasks --count 12 --seed 20260325
```

## 关键特性

- 每个任务都内置元循环解释器核心能力（闭包、递归、条件、局部作用域、多层输入解析）。
- 算术能力支持更丰富变体：
  - `basic`: `+ - * /`
  - `modulo`: `+ - * / modulo`
  - `bitwise`: `& | ^ << >>`（解释器中暴露为 `bit-and/bit-or/bit-xor/shl/shr`）
  - `comparison`: `= < > <= >=`
  - `math_ext`: `abs sqrt pow log`
  - `random`: `rand seed`（可选，默认不作为强确定性评测核心）
- 新增语法与任务类型：O(for/while)、P(vector数组)、Q(hash记录/结构体)
- 所有 `eval.scm` 支持标准输入读取与运行期输入转发，支持 `read/read-line/display/write`。
- 输出 `variants` + `arith_variant_ops` + `feature_flags`，便于差异化评测。

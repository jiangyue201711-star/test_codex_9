#!/usr/bin/env python3
"""Generate MESIS-Bench meta-circular Scheme evaluator tasks in batch."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

TASK_TYPES = {
    "A": "基础算术 (+, -, *, /)", "B": "变量定义与访问", "C": "函数定义与调用",
    "D": "递归函数（factorial, fibonacci）", "E": "闭包与高阶函数", "F": "条件分支 (if, cond)",
    "G": "多层 eval 调用自身", "H": "自宿主任务（eval.scm 调用自身生成程序）", "I": "组合任务（算术 + 函数 + eval 嵌套）",
    "J": "符号与列表程序（quote/list/map/filter/fold）", "K": "局部作用域与绑定策略（let/let*/letrec）",
    "L": "惰性求值与延迟执行（delay/force/thunk）", "M": "标准输入输出任务（read/read-line/display/write）",
    "N": "元程序任务（程序生成与apply/eval组合）", "O": "循环控制语法（for/while）",
    "P": "数组数据结构（vector）", "Q": "结构体/记录数据结构（hash作为record）",
}

ARITH_VARIANTS = {
    "basic": ["+", "-", "*", "/"],
    "modulo": ["+", "-", "*", "/", "modulo"],
    "bitwise": ["&", "|", "^", "<<", ">>"],
    "comparison": ["=", "<", ">", "<=", ">="],
    "math_ext": ["abs", "sqrt", "pow", "log"],
    "random": ["rand", "seed"],
}

ARITH_BINDINGS = {
    "+": "(cons '+ +)", "-": "(cons '- -)", "*": "(cons '* *)", "/": "(cons '/ /)", "modulo": "(cons 'modulo modulo)",
    "&": "(cons 'bit-and bitwise-and)", "|": "(cons 'bit-or bitwise-ior)", "^": "(cons 'bit-xor bitwise-xor)",
    "<<": "(cons 'shl (lambda (a b) (arithmetic-shift a b)))", ">>": "(cons 'shr (lambda (a b) (arithmetic-shift a (- b))))",
    "=": "(cons '= =)", "<": "(cons '< <)", ">": "(cons '> >)", "<=": "(cons '<= <=)", ">=": "(cons '>= >=)",
    "abs": "(cons 'abs abs)", "sqrt": "(cons 'sqrt sqrt)", "pow": "(cons 'pow expt)", "log": "(cons 'log log)",
    "rand": "(cons 'rand random)", "seed": "(cons 'seed random-seed)",
}

DIFFICULTY_LEVELS = {
    1: ["A", "B", "M"], 2: ["B", "C", "J", "M", "P"], 3: ["C", "E", "J", "N", "Q"],
    4: ["D", "F", "K", "N", "O"], 5: ["G", "I", "K", "M", "P"], 6: ["H", "G", "L", "M", "Q"],
    7: ["G", "H", "I", "K", "L", "N", "O", "P"], 8: ["A", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q"],
}


@dataclass
class TaskSpec:
    task_id: int
    difficulty: int
    task_types: list[str]
    variants: dict[str, str]


def choose_variants(task_types: list[str], task_id: int) -> dict[str, str]:
    keys = list(ARITH_VARIANTS.keys())
    arith = keys[task_id % len(keys)] if ({"A", "I"} & set(task_types)) else "basic"
    return {"arith": arith}


def feature_flags(spec: TaskSpec) -> dict[str, bool]:
    t = set(spec.task_types)
    return {
        "symbolic_list": "J" in t, "lazy_eval": "L" in t, "io_basic": "M" in t, "meta_program": "N" in t,
        "loop_syntax": "O" in t, "vector_ds": "P" in t, "record_ds": "Q" in t,
        "arith_variant": spec.variants["arith"],
    }


def primitive_block(flags: dict[str, bool], variants: dict[str, str]) -> str:
    arith_ops = ARITH_VARIANTS[variants["arith"]]
    core = [ARITH_BINDINGS[x] for x in arith_ops]
    # always keep baseline comparators for evaluator internals/tests stability
    for cmp_op in ["=", "<", ">", "<=", ">="]:
        if cmp_op not in arith_ops:
            core.append(ARITH_BINDINGS[cmp_op])
    core += [
        "(cons 'display display)", "(cons 'newline newline)", "(cons 'write write)",
        "(cons 'read read)", "(cons 'read-line read-line)",
        "(cons 'list list)", "(cons 'cons cons)", "(cons 'car car)", "(cons 'cdr cdr)",
        "(cons 'null? null?)", "(cons 'pair? pair?)", "(cons 'number? number?)", "(cons 'symbol? symbol?)",
        "(cons 'not not)", "(cons 'map map)", "(cons 'apply apply)",
    ]
    if flags["symbolic_list"]:
        core += ["(cons 'append append)", "(cons 'length length)", "(cons 'reverse reverse)", "(cons 'memq memq)"]
    if flags["lazy_eval"]:
        core += ["(cons 'force force)"]
    if flags["vector_ds"]:
        core += ["(cons 'vector vector)", "(cons 'make-vector make-vector)", "(cons 'vector-ref vector-ref)", "(cons 'vector-set! vector-set!)", "(cons 'vector-length vector-length)"]
    if flags["record_ds"]:
        core += ["(cons 'hash hash)", "(cons 'hash-ref hash-ref)", "(cons 'hash-set hash-set)"]
    return "\n   ".join(core)


def special_forms_block(flags: dict[str, bool]) -> str:
    forms = [
        "[(number? exp) exp]", "[(boolean? exp) exp]", "[(string? exp) exp]", "[(symbol? exp) (lookup env exp)]",
        "[(not (pair? exp)) exp]", "[(eq? (car exp) 'quote) (cadr exp)]",
        "[(eq? (car exp) 'if) (if (m-eval (cadr exp) env) (m-eval (caddr exp) env) (m-eval (cadddr exp) env))]",
        "[(eq? (car exp) 'cond) (m-eval (cond->if (cdr exp)) env)]", "[(eq? (car exp) 'begin) (eval-sequence (cdr exp) env)]",
        "[(eq? (car exp) 'define) (let ([name (cadr exp)] [rhs (caddr exp)]) (let ([value (m-eval rhs env)]) (set! global-env (cons (cons name value) global-env)) name))]",
        "[(eq? (car exp) 'set!) (let ([name (cadr exp)] [rhs (caddr exp)]) (set-var env name (m-eval rhs env)) 'ok)]",
        "[(eq? (car exp) 'lambda) (make-closure (cadr exp) (cddr exp) env)]",
        "[(eq? (car exp) 'let) (let* ([bindings (cadr exp)] [names (map car bindings)] [vals (map (lambda (b) (m-eval (cadr b) env)) bindings)] [n-env (extend-env names vals env)]) (eval-sequence (cddr exp) n-env))]",
        "[(eq? (car exp) 'let*) (let loop ([bs (cadr exp)] [e env]) (if (null? bs) (eval-sequence (cddr exp) e) (let* ([b (car bs)] [n (car b)] [v (m-eval (cadr b) e)]) (loop (cdr bs) (extend-env (list n) (list v) e)))))]",
        "[(eq? (car exp) 'letrec) (let* ([binding (car (cadr exp))] [name (car binding)] [rhs (cadr binding)]) (set! global-env (cons (cons name 'pending) global-env)) (set-var global-env name (m-eval rhs global-env)) (eval-sequence (cddr exp) global-env))]",
    ]
    if flags["loop_syntax"]:
        forms += [
            "[(eq? (car exp) 'while) (let loop () (if (m-eval (cadr exp) env) (begin (eval-sequence (cddr exp) env) (loop)) 'done))]",
            "[(eq? (car exp) 'for) (let* ([spec (cadr exp)] [v (car spec)] [s (m-eval (cadr spec) env)] [e (m-eval (caddr spec) env)]) (let loop ([i s]) (if (> i e) 'done (begin (set! global-env (cons (cons v i) global-env)) (eval-sequence (cddr exp) global-env) (loop (+ i 1))))))]",
        ]
    if flags["lazy_eval"]:
        forms.append("[(eq? (car exp) 'delay) (delay (m-eval (cadr exp) env))]")
    if flags["meta_program"]:
        forms.append("[(eq? (car exp) 'meta-eval) (m-eval (m-eval (cadr exp) env) env)]")
    forms.append("[else (let ([proc (m-eval (car exp) env)] [args (map (lambda (e) (m-eval e env)) (cdr exp))]) (apply-proc proc args))]")
    return "\n    ".join(forms)


def evaluator_source(spec: TaskSpec) -> str:
    flags = feature_flags(spec)
    return dedent(f"""
    #lang racket
    ;; Auto-generated by MESIS-Bench generator
    ;; task_id={spec.task_id:04d}, difficulty=L{spec.difficulty}, types=[{' '.join(spec.task_types)}]
    ;; variants={json.dumps(spec.variants, ensure_ascii=False)}
    ;; dynamic_features={json.dumps(flags, ensure_ascii=False)}

    (define (extend-env vars vals base) (append (map cons vars vals) base))
    (define (lookup env sym) (cond [(null? env) (error "unbound variable" sym)] [(eq? (caar env) sym) (cdar env)] [else (lookup (cdr env) sym)]))
    (define (set-var env sym val) (cond [(null? env) (error "cannot set! unbound variable" sym)] [(eq? (caar env) sym) (set-cdr! (car env) val)] [else (set-var (cdr env) sym val)]))

    (define primitive-env
      (list
       {primitive_block(flags, spec.variants)}))
    (define global-env primitive-env)

    (define (closure? x) (and (pair? x) (eq? (car x) 'closure)))
    (define (make-closure params body env) (list 'closure params body env))
    (define (apply-proc proc args)
      (cond [(and (pair? proc) (eq? (car proc) 'closure)) (let* ([params (cadr proc)] [body (caddr proc)] [saved-env (cadddr proc)] [next-env (extend-env params args saved-env)]) (eval-sequence body next-env))]
            [(procedure? proc) (apply proc args)] [else (error "not a procedure" proc)]))
    (define (eval-sequence exps env)
      (cond [(null? exps) '()] [(null? (cdr exps)) (m-eval (car exps) env)] [else (m-eval (car exps) env) (eval-sequence (cdr exps) env)]))
    (define (cond->if clauses)
      (if (null? clauses) #f (let ([clause (car clauses)] [rest (cdr clauses)]) (if (eq? (car clause) 'else) (cons 'begin (cdr clause)) (list 'if (car clause) (cons 'begin (cdr clause)) (cond->if rest))))))
    (define (m-eval exp env)
      (cond
        {special_forms_block(flags)}))

    (define (header-line? s) (define t (string-trim s)) (or (string-prefix? t "scheme ") (string-prefix? t "eval.scm ")))
    (define (split-input lines)
      (define (drop-headers xs) (if (and (pair? xs) (header-line? (car xs))) (drop-headers (cdr xs)) xs))
      (define payload (drop-headers lines)) (define expr-line (if (null? payload) "" (car payload))) (define runtime-lines (if (null? payload) '() (cdr payload))) (values expr-line runtime-lines))

    (define (main)
      (define all-lines (let loop ([acc '()]) (define line (read-line (current-input-port) 'any)) (if (eof-object? line) (reverse acc) (loop (cons line acc)))))
      (define-values (expr-line runtime-lines) (split-input all-lines))
      (define expr (with-input-from-string expr-line (lambda () (read))))
      (define runtime-input (if (null? runtime-lines) "" (string-append (string-join runtime-lines "\\n") "\\n")))
      (define result (parameterize ([current-input-port (open-input-string runtime-input)]) (m-eval expr global-env)))
      (cond [(void? result) (void)] [else (display result) (newline)]))
    (main)
    """).strip() + "\n"


def base_test_pool(spec: TaskSpec) -> list[dict]:
    tests = [
        {"name": "basic_arithmetic", "input": "scheme program.scm\n(+ 2 3)\n", "expected_output": "5\n", "covers": ["A"]},
        {"name": "variable_access", "input": "scheme program.scm\n(begin (define x 7) (+ x 5))\n", "expected_output": "12\n", "covers": ["B"]},
        {"name": "function_call", "input": "scheme program.scm\n((lambda (x) (+ x 4)) 6)\n", "expected_output": "10\n", "covers": ["C", "E"]},
        {"name": "while_loop", "input": "scheme program.scm\n(begin (define i 0) (define s 0) (while (< i 4) (set! s (+ s i)) (set! i (+ i 1))) s)\n", "expected_output": "6\n", "covers": ["O"]},
        {"name": "vector_ops", "input": "scheme program.scm\n(begin (define v (vector 1 2 3)) (vector-set! v 1 7) (vector-ref v 1))\n", "expected_output": "7\n", "covers": ["P"]},
        {"name": "record_hash_ops", "input": "scheme program.scm\n(hash-ref (hash 'x 10 'y 20) 'y)\n", "expected_output": "20\n", "covers": ["Q"]},
        {"name": "multi_layer_eval", "input": "scheme eval.scm\nscheme generated_eval.scm\n(+ 10 20)\n", "expected_output": "30\n", "covers": ["G", "H", "I"]},
    ]
    av = spec.variants.get("arith")
    if av == "modulo":
        tests.append({"name": "arithmetic_modulo", "input": "scheme program.scm\n(modulo 17 5)\n", "expected_output": "2\n", "covers": ["A", "I"]})
    if av == "bitwise":
        tests.append({"name": "arithmetic_bitwise", "input": "scheme program.scm\n(bit-and 6 3)\n", "expected_output": "2\n", "covers": ["A", "I"]})
    if av == "comparison":
        tests.append({"name": "arithmetic_comparison", "input": "scheme program.scm\n(<= 3 5)\n", "expected_output": "#t\n", "covers": ["A", "I"]})
    if av == "math_ext":
        tests.append({"name": "arithmetic_math_ext", "input": "scheme program.scm\n(abs -9)\n", "expected_output": "9\n", "covers": ["A", "I"]})
    if av == "random":
        tests.append({"name": "arithmetic_random_seeded", "input": "scheme program.scm\n(begin (seed 123) (rand 10))\n", "expected_output": "0\n", "covers": ["A", "I"], "note": "示例占位，具体rand输出由实现决定"})
    return tests


def build_tests(spec: TaskSpec) -> list[dict]:
    pool = base_test_pool(spec)
    types = set(spec.task_types)
    required = [dict(t) for t in pool if any(c in types for c in t["covers"])]
    fallback = [dict(t) for t in pool if t not in required]
    selected = (required + fallback)
    lambda_case = next((x for x in selected if x.get("name") == "function_call"), None)
    if lambda_case is not None:
        selected = [lambda_case] + [x for x in selected if x is not lambda_case]
    selected = selected[:5]
    if len(selected) < 3:
        selected = (required + fallback)[:3]
    for t in selected:
        t["required_for_task"] = any(c in types for c in t["covers"])
    return selected


def build_task_specs(count: int, seed: int) -> list[TaskSpec]:
    rng = random.Random(seed)
    specs = []
    for i in range(1, count + 1):
        difficulty = ((i - 1) % 8) + 1
        pool = DIFFICULTY_LEVELS[difficulty]
        k = 3 if difficulty >= 7 else 2
        task_types = sorted(rng.sample(pool, k=min(k, len(pool))))
        if difficulty in (1, 8) and not ({"A", "I"} & set(task_types)):
            task_types[0] = "A"
            task_types = sorted(set(task_types))
        specs.append(TaskSpec(i, difficulty, task_types, choose_variants(task_types, i)))
    return specs


def generate(output_dir: Path, count: int, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = build_task_specs(count, seed)
    manifest = {"generator": "MESIS-Bench eval.scm batch generator", "seed": seed, "count": count, "tasks": []}
    for spec in specs:
        stem = f"task_{spec.task_id:04d}"
        flags = feature_flags(spec)
        (output_dir / f"{stem}_eval.scm").write_text(evaluator_source(spec), encoding="utf-8")
        (output_dir / f"{stem}_tests.json").write_text(json.dumps({
            "task_id": stem, "difficulty": f"L{spec.difficulty}", "task_types": spec.task_types, "variants": spec.variants,
            "arith_variant_ops": ARITH_VARIANTS[spec.variants["arith"]],
            "task_type_descriptions": {k: TASK_TYPES[k] for k in spec.task_types}, "feature_flags": flags, "deterministic": True,
            "test_cases": build_tests(spec),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["tasks"].append({
            "task_id": stem, "difficulty": f"L{spec.difficulty}", "task_types": spec.task_types, "variants": spec.variants,
            "arith_variant_ops": ARITH_VARIANTS[spec.variants["arith"]], "feature_flags": flags,
            "eval": f"tasks/{stem}_eval.scm", "tests": f"tasks/{stem}_tests.json",
        })
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate MESIS-Bench tasks")
    parser.add_argument("--output-dir", default="tasks")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260325)
    args = parser.parse_args()
    generate(Path(args.output_dir), args.count, args.seed)
    print(f"Generated {args.count} tasks in {args.output_dir}")

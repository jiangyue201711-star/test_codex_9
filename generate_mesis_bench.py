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
    "A": "基础算术 (+, -, *, /)",
    "B": "变量定义与访问",
    "C": "函数定义与调用",
    "D": "递归函数（factorial, fibonacci）",
    "E": "闭包与高阶函数",
    "F": "条件分支 (if, cond)",
    "G": "多层 eval 调用自身",
    "H": "自宿主任务（eval.scm 调用自身生成程序）",
    "I": "组合任务（算术 + 函数 + eval 嵌套）",
    "J": "符号与列表程序（quote/list/map/filter/fold）",
    "K": "局部作用域与绑定策略（let/let*/letrec）",
    "L": "惰性求值与延迟执行（delay/force/thunk）",
}

DIFFICULTY_LEVELS = {
    1: ["A", "B"],
    2: ["B", "C", "J"],
    3: ["C", "E", "J"],
    4: ["D", "F", "K"],
    5: ["G", "I", "K"],
    6: ["H", "G", "L"],
    7: ["G", "H", "I", "K", "L"],
    8: ["A", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
}


@dataclass
class TaskSpec:
    task_id: int
    difficulty: int
    task_types: list[str]


def feature_flags(spec: TaskSpec) -> dict[str, bool]:
    t = set(spec.task_types)
    return {
        "arith": bool({"A", "I"} & t),
        "vars": bool({"B", "I", "D", "K"} & t),
        "lambda": bool({"C", "E", "I", "D", "K", "L"} & t),
        "recursion": bool({"D", "K"} & t),
        "higher_order": bool({"E", "I", "J"} & t),
        "condition": bool({"F", "D", "I", "K"} & t),
        "multi_layer": bool({"G", "H", "I"} & t),
        "self_host": "H" in t,
        "symbolic_list": "J" in t,
        "local_scope": "K" in t,
        "lazy_eval": "L" in t,
    }


def primitive_block(flags: dict[str, bool]) -> str:
    core = [
        "(cons 'display display)",
        "(cons 'newline newline)",
        "(cons 'list list)",
        "(cons 'cons cons)",
        "(cons 'car car)",
        "(cons 'cdr cdr)",
        "(cons 'null? null?)",
        "(cons 'pair? pair?)",
        "(cons 'number? number?)",
        "(cons 'symbol? symbol?)",
        "(cons 'not not)",
    ]
    if flags["arith"]:
        core.extend([
            "(cons '+ +)", "(cons '- -)", "(cons '* *)", "(cons '/ /)",
            "(cons '= =)", "(cons '< <)", "(cons '<= <=)", "(cons '> >)", "(cons '>= >=)",
        ])
    if flags["higher_order"]:
        core.extend(["(cons 'map map)", "(cons 'apply apply)"])
    if flags["symbolic_list"]:
        core.extend([
            "(cons 'append append)",
            "(cons 'length length)",
            "(cons 'reverse reverse)",
            "(cons 'memq memq)",
        ])
    if flags["lazy_eval"]:
        core.append("(cons 'force force)")
    return "\n   ".join(core)


def eval_special_forms(flags: dict[str, bool]) -> str:
    forms = [
        "[(number? exp) exp]",
        "[(boolean? exp) exp]",
        "[(string? exp) exp]",
        "[(symbol? exp) (lookup env exp)]",
        "[(not (pair? exp)) exp]",
        "[(eq? (car exp) 'quote) (cadr exp)]",
    ]

    if flags["condition"]:
        forms.extend([
            "[(eq? (car exp) 'if)\n     (if (m-eval (cadr exp) env)\n         (m-eval (caddr exp) env)\n         (m-eval (cadddr exp) env))]",
            "[(eq? (car exp) 'cond)\n     (m-eval (cond->if (cdr exp)) env)]",
        ])

    forms.append("[(eq? (car exp) 'begin) (eval-sequence (cdr exp) env)]")

    if flags["vars"]:
        forms.extend([
            "[(eq? (car exp) 'define)\n     (let ([name (cadr exp)] [rhs (caddr exp)])\n       (let ([value (m-eval rhs env)])\n         (set! global-env (cons (cons name value) global-env))\n         name))]",
            "[(eq? (car exp) 'set!)\n     (let ([name (cadr exp)] [rhs (caddr exp)])\n       (set-var env name (m-eval rhs env))\n       'ok)]",
        ])

    if flags["lambda"]:
        forms.append("[(eq? (car exp) 'lambda) (make-closure (cadr exp) (cddr exp) env)]")

    if flags["local_scope"]:
        forms.extend([
            "[(eq? (car exp) 'let)\n     (let* ([bindings (cadr exp)]\n            [names (map car bindings)]\n            [vals (map (lambda (b) (m-eval (cadr b) env)) bindings)]\n            [n-env (extend-env names vals env)])\n       (eval-sequence (cddr exp) n-env))]",
            "[(eq? (car exp) 'let*)\n     (let loop ([bs (cadr exp)] [e env])\n       (if (null? bs)\n           (eval-sequence (cddr exp) e)\n           (let* ([b (car bs)]\n                  [n (car b)]\n                  [v (m-eval (cadr b) e)])\n             (loop (cdr bs) (extend-env (list n) (list v) e)))))]",
        ])

    if flags["recursion"]:
        forms.append(
            "[(eq? (car exp) 'letrec)\n     (let* ([binding (car (cadr exp))]\n            [name (car binding)]\n            [rhs (cadr binding)])\n       (set! global-env (cons (cons name 'pending) global-env))\n       (set-var global-env name (m-eval rhs global-env))\n       (eval-sequence (cddr exp) global-env))]"
        )

    if flags["lazy_eval"]:
        forms.append("[(eq? (car exp) 'delay) (delay (m-eval (cadr exp) env))]")

    forms.append(
        "[else\n     (let ([proc (m-eval (car exp) env)]\n           [args (map (lambda (e) (m-eval e env)) (cdr exp))])\n       (apply-proc proc args))]"
    )
    return "\n    ".join(forms)


def layer_runner(flags: dict[str, bool]) -> str:
    if not flags["multi_layer"]:
        return dedent(
            """
            (define (resolve-program lines)
              (if (null? lines) "" (car (reverse lines))))
            """
        ).strip()

    host_note = "self-host aware" if flags["self_host"] else "multi-layer"
    return dedent(
        f"""
        ;; {host_note} input resolver
        (define (layer-header? line)
          (define t (string-trim line))
          (or (string-prefix? t "scheme ")
              (string-prefix? t "eval.scm ")))

        (define (resolve-program lines)
          (define (loop xs depth)
            (cond
              [(null? xs) ""]
              [(layer-header? (car xs))
               (loop (cdr xs) (+ depth 1))]
              [else (car xs)]))
          (loop lines 0))
        """
    ).strip()


def evaluator_source(spec: TaskSpec) -> str:
    flags = feature_flags(spec)
    enabled = " ".join(spec.task_types)

    cond_helper = ""
    if flags["condition"]:
        cond_helper = dedent(
            """
            (define (cond->if clauses)
              (if (null? clauses)
                  #f
                  (let ([clause (car clauses)] [rest (cdr clauses)])
                    (if (eq? (car clause) 'else)
                        (cons 'begin (cdr clause))
                        (list 'if (car clause)
                              (cons 'begin (cdr clause))
                              (cond->if rest))))))
            """
        ).strip()

    set_var_impl = dedent(
        """
        (define (set-var env sym val)
          (cond
            [(null? env) (error "cannot set! unbound variable" sym)]
            [(eq? (caar env) sym) (set-cdr! (car env) val)]
            [else (set-var (cdr env) sym val)]))
        """
    ).strip() if flags["vars"] or flags["recursion"] else ""

    lambda_impl = dedent(
        """
        (define (closure? x)
          (and (pair? x) (eq? (car x) 'closure)))

        (define (make-closure params body env)
          (list 'closure params body env))
        """
    ).strip() if flags["lambda"] else ""

    return dedent(
        f"""
        #lang racket

        ;; Auto-generated by MESIS-Bench generator
        ;; task_id={spec.task_id:04d}, difficulty=L{spec.difficulty}, types=[{enabled}]
        ;; dynamic_features={json.dumps(flags, ensure_ascii=False)}

        (define (extend-env vars vals base)
          (append (map cons vars vals) base))

        (define (lookup env sym)
          (cond
            [(null? env) (error "unbound variable" sym)]
            [(eq? (caar env) sym) (cdar env)]
            [else (lookup (cdr env) sym)]))

        {set_var_impl}

        (define primitive-env
          (list
           {primitive_block(flags)}))

        (define global-env primitive-env)

        {lambda_impl}

        (define (apply-proc proc args)
          (cond
            [(and (pair? proc) (eq? (car proc) 'closure))
             (let* ([params (cadr proc)]
                    [body (caddr proc)]
                    [saved-env (cadddr proc)]
                    [next-env (extend-env params args saved-env)])
               (eval-sequence body next-env))]
            [(procedure? proc) (apply proc args)]
            [else (error "not a procedure" proc)]))

        (define (eval-sequence exps env)
          (cond
            [(null? exps) '()]
            [(null? (cdr exps)) (m-eval (car exps) env)]
            [else
             (m-eval (car exps) env)
             (eval-sequence (cdr exps) env)]))

        {cond_helper}

        (define (m-eval exp env)
          (cond
            {eval_special_forms(flags)}))

        {layer_runner(flags)}

        (define (main)
          (define all-lines
            (let loop ([acc '()])
              (define line (read-line (current-input-port) 'any))
              (if (eof-object? line)
                  (reverse acc)
                  (loop (cons line acc)))))

          (define target (resolve-program all-lines))
          (define expr
            (with-input-from-string target
              (lambda () (read))))
          (define result (m-eval expr global-env))
          (cond
            [(void? result) (void)]
            [else (display result) (newline)]))

        (main)
        """
    ).strip() + "\n"


def base_test_pool() -> list[dict]:
    return [
        {"name": "basic_arithmetic", "input": "scheme program.scm\n(+ 2 3)\n", "expected_output": "5\n", "covers": ["A"]},
        {"name": "variable_access", "input": "scheme program.scm\n(begin (define x 7) (+ x 5))\n", "expected_output": "12\n", "covers": ["B"]},
        {"name": "function_call", "input": "scheme program.scm\n((lambda (x) (+ x 4)) 6)\n", "expected_output": "10\n", "covers": ["C"]},
        {"name": "recursive_factorial", "input": "scheme program.scm\n(begin (define fact (lambda (n) (if (= n 0) 1 (* n (fact (- n 1)))))) (fact 5))\n", "expected_output": "120\n", "covers": ["D", "F"]},
        {"name": "closure_high_order", "input": "scheme program.scm\n(begin (define make-adder (lambda (x) (lambda (y) (+ x y)))) ((make-adder 10) 5))\n", "expected_output": "15\n", "covers": ["E"]},
        {"name": "symbolic_list_ops", "input": "scheme program.scm\n(begin (define xs '(a b c)) (length xs))\n", "expected_output": "3\n", "covers": ["J"]},
        {"name": "local_scope_let_star", "input": "scheme program.scm\n(let* ((x 2) (y (+ x 3))) (* y 2))\n", "expected_output": "10\n", "covers": ["K"]},
        {"name": "lazy_delay_force", "input": "scheme program.scm\n(force (delay (+ 40 2)))\n", "expected_output": "42\n", "covers": ["L"]},
        {"name": "multi_layer_eval", "input": "scheme eval.scm\nscheme generated_eval.scm\n(+ 10 20)\n", "expected_output": "30\n", "covers": ["G", "H", "I"]},
    ]


def build_tests(spec: TaskSpec) -> list[dict]:
    pool = base_test_pool()
    types = set(spec.task_types)
    required = [t for t in pool if any(c in types for c in t["covers"])]
    fallback = [t for t in pool if t not in required]
    selected = (required + fallback)[:5]
    if len(selected) < 3:
        selected = (required + fallback)[:3]

    tests = []
    for t in selected:
        row = dict(t)
        row["required_for_task"] = any(c in types for c in row["covers"])
        tests.append(row)
    return tests


def build_task_specs(count: int, seed: int) -> list[TaskSpec]:
    rng = random.Random(seed)
    specs: list[TaskSpec] = []
    for i in range(1, count + 1):
        difficulty = ((i - 1) % 8) + 1
        pool = DIFFICULTY_LEVELS[difficulty]
        k = 3 if difficulty >= 7 and len(pool) >= 3 else min(2, len(pool))
        task_types = sorted(rng.sample(pool, k=k))
        specs.append(TaskSpec(task_id=i, difficulty=difficulty, task_types=task_types))
    return specs


def generate(output_dir: Path, count: int, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = build_task_specs(count, seed)

    manifest = {"generator": "MESIS-Bench eval.scm batch generator", "seed": seed, "count": count, "tasks": []}

    for spec in specs:
        stem = f"task_{spec.task_id:04d}"
        eval_path = output_dir / f"{stem}_eval.scm"
        tests_path = output_dir / f"{stem}_tests.json"

        flags = feature_flags(spec)
        eval_path.write_text(evaluator_source(spec), encoding="utf-8")
        tests_payload = {
            "task_id": stem,
            "difficulty": f"L{spec.difficulty}",
            "task_types": spec.task_types,
            "task_type_descriptions": {k: TASK_TYPES[k] for k in spec.task_types},
            "feature_flags": flags,
            "deterministic": True,
            "test_cases": build_tests(spec),
        }
        tests_path.write_text(json.dumps(tests_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        manifest["tasks"].append(
            {
                "task_id": stem,
                "difficulty": f"L{spec.difficulty}",
                "task_types": spec.task_types,
                "feature_flags": flags,
                "eval": str(eval_path.relative_to(output_dir.parent)),
                "tests": str(tests_path.relative_to(output_dir.parent)),
            }
        )

    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate MESIS-Bench tasks")
    parser.add_argument("--output-dir", default="tasks", help="Output tasks directory")
    parser.add_argument("--count", type=int, default=12, help="Number of tasks to generate")
    parser.add_argument("--seed", type=int, default=20260325, help="Random seed")
    args = parser.parse_args()

    generate(Path(args.output_dir), args.count, args.seed)
    print(f"Generated {args.count} tasks in {args.output_dir}")

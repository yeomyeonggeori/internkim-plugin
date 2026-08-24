#!/usr/bin/env python3

import ast
import json
import sys

MAXIMUM_EXPRESSION_LENGTH = 1024
ALLOWED_CHARACTERS = set("0123456789.+-*/%^() \t\n\r")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        run_self_test()
        return
    if len(sys.argv) != 2:
        fail('usage: calc.py "<expression>"')
    expression = sys.argv[1].strip()
    validate_expression(expression)
    result = evaluate_expression(expression)
    print(json.dumps({"expression": expression, "result": result}))


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def validate_expression(expression):
    if expression == "":
        fail("expression is required")
    if len(expression) > MAXIMUM_EXPRESSION_LENGTH:
        fail("expression is too long")
    if any(character not in ALLOWED_CHARACTERS for character in expression):
        fail("expression contains unsupported characters")
    if not parentheses_are_balanced(expression):
        fail("expression parentheses are not balanced")


def parentheses_are_balanced(expression):
    depth = 0
    for character in expression:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def evaluate_expression(expression):
    python_expression = expression.replace("^", "**")
    try:
        tree = ast.parse(python_expression, mode="eval")
    except SyntaxError:
        fail("expression is not valid arithmetic")
    try:
        value = evaluate_node(tree.body)
    except ZeroDivisionError:
        fail("expression divides by zero")
    except OverflowError:
        fail("expression result is too large")
    if isinstance(value, complex):
        fail("expression result is not a real number")
    return format_number(value)


def evaluate_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = evaluate_node(node.operand)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.BinOp):
        return apply_binary_operator(node.op, evaluate_node(node.left), evaluate_node(node.right))
    fail("expression uses an unsupported construct")


def apply_binary_operator(operator, left, right):
    if isinstance(operator, ast.Add):
        return left + right
    if isinstance(operator, ast.Sub):
        return left - right
    if isinstance(operator, ast.Mult):
        return left * right
    if isinstance(operator, ast.Div):
        return left / right
    if isinstance(operator, ast.Mod):
        return left % right
    if isinstance(operator, ast.Pow):
        return left ** right
    fail("expression uses an unsupported operator")


def format_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def run_self_test():
    expectations = {
        "(2+3)*4": "20",
        "2^10": "1024",
        "2**10": "1024",
        "1+2/4": "1.5",
        "10%3": "1",
        "-(2+3)": "-5",
    }
    for expression, expected_result in expectations.items():
        actual_result = evaluate_expression(expression)
        if actual_result != expected_result:
            fail(f"self-test failed: {expression} -> {actual_result}, expected {expected_result}")
    print(json.dumps({"selfTest": "ok", "checkedCount": len(expectations)}))


if __name__ == "__main__":
    main()

"""Python-focused EBNF parser and AST demo.

The module implements a small but meaningful subset of the Python language:

    Program      = { Statement } ;
    Statement    = Assignment | IfStmt | WhileStmt | ReturnStmt | ExprStmt ;
    Assignment   = Identifier, "=", Expression, NEWLINE ;
    IfStmt       = "if", Expression, ":", Suite,
                   { "elif", Expression, ":", Suite },
                   [ "else", ":", Suite ] ;
    WhileStmt    = "while", Expression, ":", Suite ;
    ReturnStmt   = "return", [ Expression ], NEWLINE ;
    ExprStmt     = Expression, NEWLINE ;
    Suite        = NEWLINE, INDENT, { Statement }, DEDENT ;
    Expression   = OrExpr ;
    OrExpr       = AndExpr, { "or", AndExpr } ;
    AndExpr      = CompareExpr, { "and", CompareExpr } ;
    CompareExpr  = AddExpr, [ CompOp, AddExpr ] ;
    AddExpr      = MulExpr, { ("+" | "-"), MulExpr } ;
    MulExpr      = UnaryExpr, { ("*" | "/" | "%" | "//"), UnaryExpr } ;
    UnaryExpr    = [ ("+" | "-") ], Primary ;
    Primary      = NUMBER | STRING | "True" | "False" | "None" | Identifier | "(", Expression, ")" ;

The parser accepts Python-style assignment, arithmetic, booleans, and if/else
blocks while staying intentionally compact for teaching and demonstration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable


class ParseError(ValueError):
    """Raised when source text does not conform to the supported Python subset."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int
    line: int = 0
    column: int = 0


PYTHON_KEYWORDS = {
    "and",
    "elif",
    "else",
    "False",
    "if",
    "in",
    "is",
    "not",
    "None",
    "or",
    "return",
    "True",
    "while",
    "break",
    "continue",
    "pass",
    "def",
    "for",
    "class",
    "lambda",
}

COMPARISON_OPS = {"<", ">", "<=", ">=", "==", "!=", "in", "not in", "is", "is not"}

GRAMMAR = '''Program = { Statement } ;
Statement = Assignment | IfStmt | WhileStmt | ReturnStmt | ExprStmt ;
Assignment = Identifier, "=", Expression, NEWLINE ;
IfStmt = "if", Expression, ":", Suite,
         { "elif", Expression, ":", Suite },
         [ "else", ":", Suite ] ;
WhileStmt = "while", Expression, ":", Suite ;
ReturnStmt = "return", [ Expression ], NEWLINE ;
ExprStmt = Expression, NEWLINE ;
Suite = NEWLINE, INDENT, { Statement }, DEDENT ;
Expression = OrExpr ;
OrExpr = AndExpr, { "or", AndExpr } ;
AndExpr = CompareExpr, { "and", CompareExpr } ;
CompareExpr = AddExpr, [ CompOp, AddExpr ] ;
AddExpr = MulExpr, { ("+" | "-"), MulExpr } ;
MulExpr = UnaryExpr, { ("*" | "/" | "%" | "//"), UnaryExpr } ;
UnaryExpr = [ ("+" | "-") ], Primary ;
Primary = NUMBER | STRING | "True" | "False" | "None" | Identifier | "(", Expression, ")" ;'''

TOKEN_RE = re.compile(
    r"""
    (?P<WS>[ \t]+)
  | (?P<NUMBER>\d+\.\d+|\d+)
  | (?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<OP>\*\*|//|<=|>=|==|!=|:=|[()+\-*/%<>=,:.])
  | (?P<KEYWORD>if|elif|else|while|for|in|return|and|or|not|True|False|None|pass|break|continue|class|def|lambda)\b
  | (?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<INVALID>.)
    """,
    re.VERBOSE,
)


def tokenize(source: str) -> list[Token]:
    """Convert Python source into a stream of tokens with indentation tracking."""
    tokens: list[Token] = []
    lines = source.splitlines(True)
    indent_stack = [0]
    absolute_position = 0

    for line_number, raw_line in enumerate(lines, start=1):
        if raw_line.endswith("\r\n"):
            line = raw_line[:-2]
        elif raw_line.endswith("\n") or raw_line.endswith("\r"):
            line = raw_line[:-1]
        else:
            line = raw_line

        if not line.strip() or line.lstrip().startswith("#"):
            absolute_position += len(raw_line)
            continue

        leading = len(line) - len(line.lstrip(" \t"))
        while leading < indent_stack[-1]:
            indent_stack.pop()
            tokens.append(Token("DEDENT", "", absolute_position, line_number, leading))

        if leading > indent_stack[-1]:
            indent_stack.append(leading)
            tokens.append(Token("INDENT", "", absolute_position, line_number, leading))

        if leading != indent_stack[-1]:
            raise ParseError(f"Inconsistent indentation on line {line_number}")

        cursor = 0
        while cursor < len(line):
            remainder = line[cursor:]
            if remainder.startswith("#"):
                break
            if remainder[0].isspace():
                cursor += 1
                continue
            match = TOKEN_RE.match(remainder)
            if match is None:
                raise ParseError(f"Unexpected character {remainder[0]!r} at line {line_number}, column {cursor + 1}")
            kind = match.lastgroup
            value = match.group(0)
            if kind == "WS":
                cursor += len(value)
                continue
            token_kind = kind
            if token_kind == "KEYWORD" and value in PYTHON_KEYWORDS:
                token_kind = "KEYWORD"
            elif token_kind == "IDENTIFIER":
                token_kind = "IDENTIFIER"
            elif token_kind == "NUMBER":
                token_kind = "NUMBER"
            elif token_kind == "STRING":
                token_kind = "STRING"
            elif token_kind == "OP":
                token_kind = "OP"
            if token_kind == "INVALID":
                raise ParseError(f"Unexpected token {value!r} at line {line_number}, column {cursor + 1}")
            tokens.append(Token(token_kind, value, absolute_position + cursor, line_number, cursor + 1))
            cursor += len(value)

        tokens.append(Token("NEWLINE", "\n", absolute_position + len(line), line_number, len(line) + 1))
        absolute_position += len(raw_line)

    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token("DEDENT", "", absolute_position, len(lines), 0))

    tokens.append(Token("EOF", "", absolute_position, len(lines) + 1, 0))
    return tokens


class Parser:
    """Small recursive-descent parser for the supported Python subset."""

    def __init__(self, tokens: Iterable[Token]):
        self.tokens = list(tokens)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    @property
    def previous(self) -> Token:
        return self.tokens[self.index - 1]

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        return token

    def peek(self, offset: int = 1) -> Token:
        index = self.index + offset
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def match(self, *values: str) -> bool:
        if self.current.value in values:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        if self.current.value != value:
            raise ParseError(f"Expected {value!r}, found {self.current.value or 'end of input'} at position {self.current.position}")
        return self.advance()

    def expect_kind(self, kind: str) -> Token:
        if self.current.kind != kind:
            raise ParseError(f"Expected {kind}, found {self.current.value or 'end of input'} at position {self.current.position}")
        return self.advance()

    def parse(self) -> tuple[dict[str, Any], dict[str, Any]]:
        program = {"rule": "Program", "children": []}
        while self.current.kind not in {"EOF", "DEDENT"}:
            if self.current.kind == "NEWLINE":
                self.advance()
                continue
            program["children"].append(self.statement_cst())
        return program, self.ast_from_node(program)

    def statement_cst(self) -> dict[str, Any]:
        if self.current.kind == "NEWLINE":
            self.advance()
            return self.statement_cst()
        if self.current.kind == "INDENT":
            self.advance()
            return self.statement_cst()
        if self.current.kind == "KEYWORD" and self.current.value == "if":
            return self.if_cst()
        if self.current.kind == "KEYWORD" and self.current.value == "while":
            return self.while_cst()
        if self.current.kind == "KEYWORD" and self.current.value == "return":
            return self.return_cst()
        if self.current.kind == "IDENTIFIER" and self.peek().value in {"=", "+=", "-=", "*=", "/=", "%="}:
            return self.assignment_cst()
        return self.expr_stmt_cst()

    def assignment_cst(self) -> dict[str, Any]:
        target = self.leaf(self.expect_kind("IDENTIFIER"))
        operation = self.current.value
        if operation in {"=", "+=", "-=", "*=", "/=", "%="}:
            operator = self.leaf(self.advance())
        else:
            raise ParseError(f"Unsupported assignment operator {self.current.value!r}")
        value = self.expression_cst()
        if self.current.kind == "NEWLINE":
            self.advance()
        return {"rule": "Assignment", "children": [target, operator, value]}

    def if_cst(self) -> dict[str, Any]:
        keyword = self.leaf(self.expect("if"))
        test = self.expression_cst()
        self.expect(":")
        body = self.block_cst()
        elif_branches = []
        while self.current.kind == "KEYWORD" and self.current.value == "elif":
            elif_kw = self.leaf(self.advance())
            elif_test = self.expression_cst()
            self.expect(":")
            elif_body = self.block_cst()
            elif_branches.append({"rule": "ElifClause", "children": [elif_kw, elif_test, elif_body]})
        else_body = None
        if self.current.kind == "KEYWORD" and self.current.value == "else":
            else_kw = self.leaf(self.advance())
            self.expect(":")
            else_body = self.block_cst()
            else_body = {"rule": "ElseClause", "children": [else_kw, else_body]}
        children = [keyword, test, body]
        children.extend(elif_branches)
        if else_body is not None:
            children.append(else_body)
        return {"rule": "IfStmt", "children": children}

    def while_cst(self) -> dict[str, Any]:
        keyword = self.leaf(self.expect("while"))
        test = self.expression_cst()
        self.expect(":")
        body = self.block_cst()
        return {"rule": "WhileStmt", "children": [keyword, test, body]}

    def return_cst(self) -> dict[str, Any]:
        keyword = self.leaf(self.expect("return"))
        value = None
        if self.current.kind not in {"NEWLINE", "EOF", "DEDENT"}:
            value = self.expression_cst()
        if self.current.kind == "NEWLINE":
            self.advance()
        return {"rule": "ReturnStmt", "children": [keyword, value] if value is not None else [keyword]}

    def expr_stmt_cst(self) -> dict[str, Any]:
        expression = self.expression_cst()
        if self.current.kind == "NEWLINE":
            self.advance()
        return {"rule": "ExprStmt", "children": [expression]}

    def block_cst(self) -> dict[str, Any]:
        if self.current.kind == "NEWLINE":
            self.advance()
        if self.current.kind == "INDENT":
            self.advance()
            statements: list[dict[str, Any]] = []
            while self.current.kind not in {"DEDENT", "EOF"}:
                if self.current.kind == "NEWLINE":
                    self.advance()
                    continue
                statements.append(self.statement_cst())
            if self.current.kind == "DEDENT":
                self.advance()
            return {"rule": "Block", "children": statements}
        statement = self.statement_cst()
        return {"rule": "Block", "children": [statement]}

    def expression_cst(self) -> dict[str, Any]:
        return self.or_expr_cst()

    def or_expr_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.and_expr_cst, {"or"}, "OrExpr")

    def and_expr_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.compare_expr_cst, {"and"}, "AndExpr")

    def compare_expr_cst(self) -> dict[str, Any]:
        left = self.add_expr_cst()
        children = [left]
        while self.current.kind == "OP" and self.current.value in COMPARISON_OPS:
            children.append(self.leaf(self.advance()))
            children.append(self.add_expr_cst())
        return {"rule": "CompareExpr", "children": children}

    def add_expr_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.mul_expr_cst, {"+", "-"}, "AddExpr")

    def mul_expr_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.unary_expr_cst, {"*", "/", "%", "//"}, "MulExpr")

    def unary_expr_cst(self) -> dict[str, Any]:
        if self.current.kind == "OP" and self.current.value in {"+", "-"}:
            operator = self.leaf(self.advance())
            return {"rule": "UnaryExpr", "children": [operator, self.unary_expr_cst()]}
        return self.power_expr_cst()

    def power_expr_cst(self) -> dict[str, Any]:
        left = self.primary_cst()
        if self.current.kind == "OP" and self.current.value == "**":
            operator = self.leaf(self.advance())
            right = self.unary_expr_cst()
            return {"rule": "PowerExpr", "children": [left, operator, right]}
        return left

    def primary_cst(self) -> dict[str, Any]:
        if self.current.kind == "NUMBER":
            return {"rule": "NumberLiteral", "children": [self.leaf(self.advance())]}
        if self.current.kind == "STRING":
            return {"rule": "StringLiteral", "children": [self.leaf(self.advance())]}
        if self.current.kind == "KEYWORD" and self.current.value in {"True", "False", "None"}:
            return {"rule": "BooleanLiteral", "children": [self.leaf(self.advance())]}
        if self.current.kind == "IDENTIFIER":
            name = self.leaf(self.advance())
            if self.current.value == "(":
                self.expect("(")
                args = []
                if self.current.value != ")":
                    args.append(self.expression_cst())
                    while self.current.value == ",":
                        self.advance()
                        args.append(self.expression_cst())
                self.expect(")")
                return {"rule": "Call", "children": [name, *args]}
            return {"rule": "Identifier", "children": [name]}
        if self.current.value == "(":
            self.expect("(")
            inner = self.expression_cst()
            self.expect(")")
            return {"rule": "Grouping", "children": [inner]}
        raise ParseError(f"Expected an expression, found {self.current.value or 'end of input'} at position {self.current.position}")

    def binary_cst(self, operand_builder, operators: set[str], rule: str) -> dict[str, Any]:
        left = operand_builder()
        children = [left]
        while True:
            current = self.current
            if current.kind == "KEYWORD" and current.value in operators:
                token = self.leaf(self.advance())
                right = operand_builder()
                children.extend([token, right])
                continue
            if current.kind == "OP" and current.value in operators:
                token = self.leaf(self.advance())
                right = operand_builder()
                children.extend([token, right])
                continue
            break
        return {"rule": rule, "children": children}

    @staticmethod
    def leaf(token: Token) -> dict[str, Any]:
        return {"terminal": token.value, "kind": token.kind, "position": token.position}

    def ast_from_node(self, node: dict[str, Any]) -> Any:
        rule = node["rule"]
        children = node.get("children", [])

        if rule == "Program":
            return {"type": "Module", "body": [self.ast_from_node(child) for child in children]}
        if rule == "Block":
            return [self.ast_from_node(child) for child in children]
        if rule == "ExprStmt":
            return self.ast_from_node(children[0])
        if rule == "Assignment":
            target = {"type": "Name", "id": children[0]["terminal"]}
            value = self.ast_from_node(children[2])
            return {"type": "Assign", "target": target, "value": value, "operator": children[1]["terminal"]}
        if rule == "ReturnStmt":
            if not children:
                return {"type": "Return", "value": None}
            return {"type": "Return", "value": self.ast_from_node(children[-1])}
        if rule == "IfStmt":
            body = self.ast_from_node(children[2])
            result = {"type": "If", "test": self.ast_from_node(children[1]), "body": body}
            for child in children[3:]:
                if child.get("rule") == "ElifClause":
                    elif_clause = child["children"]
                    if "elif" not in result:
                        result["elif"] = []
                    result["elif"].append({"type": "If", "test": self.ast_from_node(elif_clause[1]), "body": self.ast_from_node(elif_clause[2])})
                if child.get("rule") == "ElseClause":
                    result["else"] = self.ast_from_node(child["children"][1])
            return result
        if rule == "WhileStmt":
            return {"type": "While", "test": self.ast_from_node(children[1]), "body": self.ast_from_node(children[2])}
        if rule in {"OrExpr", "AndExpr", "AddExpr", "MulExpr", "CompareExpr"}:
            left = self.ast_from_node(children[0])
            for index in range(1, len(children), 2):
                left = {
                    "type": "BinOp",
                    "op": children[index]["terminal"],
                    "left": left,
                    "right": self.ast_from_node(children[index + 1]),
                }
            return left
        if rule == "UnaryExpr":
            return {"type": "UnaryOp", "op": children[0]["terminal"], "operand": self.ast_from_node(children[1])}
        if rule == "PowerExpr":
            return {"type": "BinOp", "op": "**", "left": self.ast_from_node(children[0]), "right": self.ast_from_node(children[2])}
        if rule == "Grouping":
            return self.ast_from_node(children[0])
        if rule == "NumberLiteral":
            value = children[0]["terminal"]
            return {"type": "Constant", "value": float(value) if "." in value else int(value)}
        if rule == "StringLiteral":
            return {"type": "Constant", "value": json.loads(children[0]["terminal"])}
        if rule == "BooleanLiteral":
            return {"type": "Constant", "value": children[0]["terminal"] == "True"}
        if rule == "Identifier":
            return {"type": "Name", "id": children[0]["terminal"]}
        if rule == "Call":
            function = self.ast_from_node(children[0])
            arguments = [self.ast_from_node(child) for child in children[1:]]
            return {"type": "Call", "function": function, "arguments": arguments}
        raise ParseError(f"Unsupported syntax rule {rule!r}")


def parse_source(source: str) -> dict[str, Any]:
    """Parse source and return both the concrete parse tree and the AST."""
    parser = Parser(tokenize(source))
    program, ast = parser.parse()
    return {"parse_tree": program, "ast": ast}


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a Python subset and output its CST and AST.")
    parser.add_argument("source", nargs="?", help="source text; omit to read from standard input")
    parser.add_argument("--ebnf", action="store_true", help="print the supported EBNF grammar before parsing")
    args = parser.parse_args()
    source = args.source if args.source is not None else sys.stdin.read()

    try:
        if args.ebnf:
            print(GRAMMAR)
        print(json.dumps(parse_source(source), indent=2, ensure_ascii=False))
    except ParseError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

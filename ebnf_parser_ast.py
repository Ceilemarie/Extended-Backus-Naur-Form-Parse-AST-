"""A small EBNF-inspired parser and AST demo.

The module implements the language described in README.md:

    Program   = { Statement } ;
    Statement = VarDecl | IfStmt | WhileStmt | Assignment ;
    Expr      = equality ;

It is deliberately self-contained so it can be uploaded as one Python file.
The public ``parse_source`` function returns both a concrete parse tree and an
abstract syntax tree.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import json
import re
from typing import Any, Iterable, NoReturn


class ParseError(ValueError):
    """Raised when source text does not conform to the mini-language grammar."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True)
class Program:
    statements: list[Any]


@dataclass(frozen=True)
class VarDeclaration:
    name: str
    initializer: Any


@dataclass(frozen=True)
class Assignment:
    name: str
    value: Any


@dataclass(frozen=True)
class IfStatement:
    condition: Any
    then_branch: list[Any]
    else_branch: list[Any] | None = None


@dataclass(frozen=True)
class WhileStatement:
    condition: Any
    body: list[Any]


@dataclass(frozen=True)
class BinaryExpression:
    operator: str
    left: Any
    right: Any


@dataclass(frozen=True)
class UnaryExpression:
    operator: str
    operand: Any


@dataclass(frozen=True)
class Literal:
    value: int | bool


@dataclass(frozen=True)
class Identifier:
    name: str


TOKEN_RE = re.compile(
    r"""
    (?P<WHITESPACE>\s+)
  | (?P<COMMENT>//[^\n]*)
  | (?P<NUMBER>\d+)
  | (?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP>==|!=|<=|>=|[+\-*/<>=])
  | (?P<PUNCT>[;(),{}])
    """,
    re.VERBOSE,
)

KEYWORDS = {"let", "const", "var", "if", "else", "while", "true", "false"}


def tokenize(source: str) -> list[Token]:
    """Convert source text into tokens and reject unknown characters."""
    tokens: list[Token] = []
    position = 0
    while position < len(source):
        match = TOKEN_RE.match(source, position)
        if match is None:
            raise ParseError(f"Unexpected character {source[position]!r} at {position}")

        kind = match.lastgroup
        value = match.group()
        if kind not in {"WHITESPACE", "COMMENT"}:
            if kind == "IDENTIFIER" and value in KEYWORDS:
                kind = "KEYWORD"
            tokens.append(Token(kind, value, position))
        position = match.end()

    tokens.append(Token("EOF", "", len(source)))
    return tokens


class Parser:
    """Recursive-descent parser with standard operator precedence."""

    def __init__(self, tokens: Iterable[Token]):
        self.tokens = list(tokens)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        return token

    def check(self, value: str) -> bool:
        return self.current.value == value

    def match(self, *values: str) -> bool:
        if self.current.value in values:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        if not self.check(value):
            self.error(f"Expected {value!r}, found {self.current.value or 'end of input'!r}")
        return self.advance()

    def expect_kind(self, kind: str) -> Token:
        if self.current.kind != kind:
            self.error(f"Expected {kind}, found {self.current.value or 'end of input'!r}")
        return self.advance()

    def error(self, message: str) -> NoReturn:
        raise ParseError(f"{message} at position {self.current.position}")

    def parse(self) -> tuple[Program, dict[str, Any]]:
        """Return an AST and a concrete parse tree for the complete program."""
        cst = self.program_cst()
        if self.current.kind != "EOF":
            self.error(f"Unexpected token {self.current.value!r}")
        return self.ast_from_program_cst(cst), cst

    def program_cst(self) -> dict[str, Any]:
        children = []
        while self.current.kind != "EOF":
            children.append(self.statement_cst())
        return {"rule": "Program", "children": children}

    def statement_cst(self) -> dict[str, Any]:
        if self.current.value in {"let", "const", "var"}:
            return self.var_decl_cst()
        if self.check("if"):
            return self.if_cst()
        if self.check("while"):
            return self.while_cst()
        if self.current.kind == "IDENTIFIER":
            return self.assignment_cst()
        self.error(f"Expected a statement, found {self.current.value!r}")

    def var_decl_cst(self) -> dict[str, Any]:
        keyword = self.leaf(self.advance())
        name = self.leaf(self.expect_kind("IDENTIFIER"))
        equals = self.leaf(self.expect("="))
        expression = self.expression_cst()
        semicolon = self.leaf(self.expect(";"))
        return {"rule": "VarDecl", "children": [keyword, name, equals, expression, semicolon]}

    def assignment_cst(self) -> dict[str, Any]:
        name = self.leaf(self.expect_kind("IDENTIFIER"))
        equals = self.leaf(self.expect("="))
        expression = self.expression_cst()
        semicolon = self.leaf(self.expect(";"))
        return {"rule": "Assignment", "children": [name, equals, expression, semicolon]}

    def if_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("if")), self.leaf(self.expect("("))]
        children.append(self.expression_cst())
        children.extend([self.leaf(self.expect(")")), self.block_cst()])
        if self.match("else"):
            children.extend([self.leaf(self.tokens[self.index - 1]), self.block_cst()])
        return {"rule": "IfStmt", "children": children}

    def while_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("while")), self.leaf(self.expect("("))]
        children.extend([self.expression_cst(), self.leaf(self.expect(")")), self.block_cst()])
        return {"rule": "WhileStmt", "children": children}

    def block_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("{"))]
        while not self.check("}") and self.current.kind != "EOF":
            children.append(self.statement_cst())
        children.append(self.leaf(self.expect("}")))
        return {"rule": "Block", "children": children}

    def expression_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.equality_cst, {"==", "!="}, "Equality")

    def equality_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.comparison_cst, {"<", "<=", ">", ">="}, "Comparison")

    def comparison_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.term_cst, {"+", "-"}, "Term")

    def term_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.factor_cst, {"*", "/"}, "Factor")

    def binary_cst(self, operand, operators: set[str], rule: str) -> dict[str, Any]:
        left = operand()
        children = [left]
        while self.current.value in operators:
            children.append(self.leaf(self.advance()))
            children.append(operand())
        return {"rule": rule, "children": children}

    def factor_cst(self) -> dict[str, Any]:
        if self.match("-", "+"):
            operator = self.tokens[self.index - 1]
            return {
                "rule": "Unary",
                "children": [self.leaf(operator), self.factor_cst()],
            }
        if self.match("("):
            expression = self.expression_cst()
            return {
                "rule": "Grouping",
                "children": [
                    self.leaf(self.tokens[self.index - 1]),
                    expression,
                    self.leaf(self.expect(")")),
                ],
            }
        if self.current.kind == "NUMBER":
            return {"rule": "IntLiteral", "children": [self.leaf(self.advance())]}
        if self.current.kind == "KEYWORD" and self.current.value in {"true", "false"}:
            return {"rule": "BooleanLiteral", "children": [self.leaf(self.advance())]}
        if self.current.kind == "IDENTIFIER":
            return {"rule": "Identifier", "children": [self.leaf(self.advance())]}
        self.error(f"Expected an expression, found {self.current.value!r}")

    @staticmethod
    def leaf(token: Token) -> dict[str, Any]:
        return {"terminal": token.value, "kind": token.kind, "position": token.position}

    def ast_from_program_cst(self, cst: dict[str, Any]) -> Program:
        return Program([self.ast_from_statement(node) for node in cst["children"]])

    def ast_from_statement(self, node: dict[str, Any]) -> Any:
        rule = node["rule"]
        children = node["children"]
        if rule in {"VarDecl", "Assignment"}:
            name = children[1]["terminal"]
            expression_index = 3 if rule == "VarDecl" else 2
            value = self.ast_from_expression(children[expression_index])
            return VarDeclaration(name, value) if rule == "VarDecl" else Assignment(name, value)
        if rule == "IfStmt":
            condition = self.ast_from_expression(children[2])
            then_branch = self.ast_from_block(children[4])
            else_branch = self.ast_from_block(children[6]) if len(children) == 7 else None
            return IfStatement(condition, then_branch, else_branch)
        if rule == "WhileStmt":
            return WhileStatement(self.ast_from_expression(children[2]), self.ast_from_block(children[4]))
        raise ParseError(f"Unsupported statement rule {rule!r}")

    def ast_from_block(self, node: dict[str, Any]) -> list[Any]:
        return [self.ast_from_statement(child) for child in node["children"][1:-1]]

    def ast_from_expression(self, node: dict[str, Any]) -> Any:
        rule = node["rule"]
        children = node["children"]
        if rule in {"Equality", "Comparison", "Term", "Factor"}:
            result = self.ast_from_expression(children[0])
            for index in range(1, len(children), 2):
                result = BinaryExpression(
                    children[index]["terminal"],
                    result,
                    self.ast_from_expression(children[index + 1]),
                )
            return result
        if rule == "Unary":
            return UnaryExpression(children[0]["terminal"], self.ast_from_expression(children[1]))
        if rule == "Grouping":
            return self.ast_from_expression(children[1])
        if rule == "IntLiteral":
            return Literal(int(children[0]["terminal"]))
        if rule == "BooleanLiteral":
            return Literal(children[0]["terminal"] == "true")
        if rule == "Identifier":
            return Identifier(children[0]["terminal"])
        raise ParseError(f"Unsupported expression rule {rule!r}")


def parse_source(source: str) -> dict[str, Any]:
    """Parse source and return JSON-serializable ``parse_tree`` and ``ast``."""
    ast, parse_tree = Parser(tokenize(source)).parse()
    return {"parse_tree": parse_tree, "ast": to_dict(ast)}


def to_dict(value: Any) -> Any:
    """Convert AST dataclasses and nested lists into ordinary Python values."""
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            **{field.name: to_dict(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    return value


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Parse the EBNF mini-language and print its CST and AST.")
    parser.add_argument("source", nargs="?", help="source text; omit to read from standard input")
    args = parser.parse_args()
    source = args.source if args.source is not None else input()
    try:
        print(json.dumps(parse_source(source), indent=2))
    except ParseError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

"""A small EBNF-driven parser that produces a concrete tree and an AST.

The language is intentionally small and suitable for demonstrating compiler
front-end concepts:

    Program       = { Statement } ;
    Statement     = VarDecl | Assignment | IfStmt ;
    VarDecl       = ("let" | "const" | "var") Identifier "=" Expression ";" ;
    Assignment    = Identifier "=" Expression ";" ;
    IfStmt        = "if" "(" Expression ")" Block [ "else" Block ] ;
    Block         = "{" { Statement } "}" ;
    Expression    = Comparison { ("==" | "!=") Comparison } ;
    Comparison    = Term { ("<" | "<=" | ">" | ">=") Term } ;
    Term          = Factor { ("+" | "-") Factor } ;
    Factor        = Unary { ("*" | "/" | "%") Unary } ;
    Unary         = ("+" | "-") Unary | Primary ;
    Primary       = Number | String | Boolean | Identifier
                  | "(" Expression ")" ;

Simple statements require a semicolon. Whitespace and comments are ignored.
The public ``parse_source`` function returns JSON-serializable parse-tree and
AST data, and ``main`` provides a console interface.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import argparse
import json
import re
import sys
from typing import Any, Iterable, NoReturn


EBNF_GRAMMAR = """\
Program       = { Statement } ;
Statement     = VarDecl | Assignment | IfStmt ;
VarDecl       = ("let" | "const" | "var") Identifier "=" Expression ";" ;
Assignment    = Identifier "=" Expression ";" ;
IfStmt        = "if" "(" Expression ")" Block [ "else" Block ] ;
Block         = "{" { Statement } "}" ;
Expression    = Comparison { ("==" | "!=") Comparison } ;
Comparison    = Term { ("<" | "<=" | ">" | ">=") Term } ;
Term          = Factor { ("+" | "-") Factor } ;
Factor        = Unary { ("*" | "/" | "%") Unary } ;
Unary         = ("+" | "-") Unary | Primary ;
Primary       = Number | String | Boolean | Identifier | "(" Expression ")" ;
"""


class ParseError(ValueError):
    """Raised when source text does not match the grammar."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int
    line: int
    column: int


@dataclass(frozen=True)
class Program:
    statements: list[Any]


@dataclass(frozen=True)
class VarDeclaration:
    keyword: str
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
    else_branch: list[Any] | None


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
    value: Any


@dataclass(frozen=True)
class Identifier:
    name: str


TOKEN_RE = re.compile(
    r"""
    (?P<WHITESPACE>[ \t\r]+)
  | (?P<NEWLINE>\n)
  | (?P<COMMENT>\#[^\n]*)
  | (?P<STRING>"(?:\\.|[^"\n])*"|'(?:\\.|[^'\n])*')
  | (?P<NUMBER>\d+(?:\.\d+)?)
  | (?P<OP>==|!=|<=|>=|[+\-*/%<>=();{}])
  | (?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)

KEYWORDS = {"let", "const", "var", "if", "else", "true", "false"}


def tokenize(source: str) -> list[Token]:
    """Tokenize source and report the exact line and column of bad input."""
    tokens: list[Token] = []
    position = 0
    line = 1
    column = 1
    while position < len(source):
        match = TOKEN_RE.match(source, position)
        if match is None:
            char = source[position]
            raise ParseError(f"Unexpected character {char!r} at line {line}, column {column}")
        kind = match.lastgroup
        value = match.group()
        token = Token(
            "KEYWORD" if kind == "IDENTIFIER" and value in KEYWORDS else kind,
            value,
            position,
            line,
            column,
        )
        if kind not in {"WHITESPACE", "NEWLINE", "COMMENT"}:
            tokens.append(token)
        line += value.count("\n")
        column = column + len(value) if "\n" not in value else len(value.rsplit("\n", 1)[-1]) + 1
        position = match.end()
    tokens.append(Token("EOF", "", len(source), line, column))
    return tokens


class Parser:
    """Recursive-descent parser with arithmetic and comparison precedence."""

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

    def error(self, message: str) -> NoReturn:
        token = self.current
        raise ParseError(f"{message} at line {token.line}, column {token.column}")

    def parse(self) -> tuple[Program, dict[str, Any]]:
        tree = self.program_cst()
        return self.ast_from_program(tree), tree

    def program_cst(self) -> dict[str, Any]:
        children = []
        while self.current.kind != "EOF":
            children.append(self.statement_cst())
        return {"rule": "Program", "children": children}

    def statement_cst(self) -> dict[str, Any]:
        if self.current.kind == "NEWLINE":
            self.advance()
            return self.statement_cst()
        if self.current.kind == "INDENT":
            self.advance()
            return self.statement_cst()
        if self.current.kind == "KEYWORD" and self.current.value == "if":
            return self.if_cst()
        if self.current.kind == "IDENTIFIER":
            return self.assignment_cst()
        self.error("Expected a variable declaration, assignment, or if statement")

    def var_decl_cst(self) -> dict[str, Any]:
        keyword = self.leaf(self.advance())
        name = self.leaf(self.expect_kind("IDENTIFIER"))
        equals = self.leaf(self.expect("="))
        expression = self.expression_cst()
        semicolon = self.leaf(self.expect(";"))
        return {"rule": "VarDecl", "children": [keyword, name, equals, expression, semicolon]}

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
        children = [self.leaf(self.expect("if")), self.leaf(self.expect("("))]
        children.extend([self.expression_cst(), self.leaf(self.expect(")")), self.block_cst()])
        if self.match("else"):
            children.extend([self.leaf(self.tokens[self.index - 1]), self.block_cst()])
        return {"rule": "IfStmt", "children": children}

    def block_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("{"))]
        while not self.check("}") and self.current.kind != "EOF":
            children.append(self.statement_cst())
        if self.current.kind == "EOF":
            self.error("Expected '}' to close block")
        children.append(self.leaf(self.expect("}")))
        return {"rule": "Block", "children": children}

    def expression_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.comparison_cst, {"==", "!="}, "Expression")

    def comparison_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.term_cst, {"<", "<=", ">", ">="}, "Comparison")

    def term_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.factor_cst, {"+", "-"}, "Term")

    def factor_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.unary_cst, {"*", "/", "%"}, "Factor")

    def binary_cst(self, operand: Any, operators: set[str], rule: str) -> dict[str, Any]:
        children = [operand()]
        while self.current.value in operators:
            children.extend([self.leaf(self.advance()), operand()])
        return {"rule": rule, "children": children}

    def unary_cst(self) -> dict[str, Any]:
        if self.match("+", "-"):
            return {"rule": "Unary", "children": [self.leaf(self.tokens[self.index - 1]), self.unary_cst()]}
        return self.primary_cst()

    def primary_cst(self) -> dict[str, Any]:
        if self.match("("):
            opening = self.tokens[self.index - 1]
            expression = self.expression_cst()
            return {"rule": "Grouping", "children": [self.leaf(opening), expression, self.leaf(self.expect(")"))]}
        if self.current.kind == "NUMBER":
            return {"rule": "Number", "children": [self.leaf(self.advance())]}
        if self.current.kind == "STRING":
            return {"rule": "String", "children": [self.leaf(self.advance())]}
        if self.current.value in {"true", "false"}:
            return {"rule": "Boolean", "children": [self.leaf(self.advance())]}
        if self.current.kind == "IDENTIFIER":
            return {"rule": "Identifier", "children": [self.leaf(self.advance())]}
        self.error("Expected a number, string, boolean, identifier, or parenthesized expression")

    @staticmethod
    def leaf(token: Token) -> dict[str, Any]:
        return {
            "terminal": token.value,
            "kind": token.kind,
            "position": token.position,
            "line": token.line,
            "column": token.column,
        }

    def ast_from_program(self, node: dict[str, Any]) -> Program:
        return Program([self.ast_from_statement(child) for child in node["children"]])

    def ast_from_statement(self, node: dict[str, Any]) -> Any:
        children = node["children"]
        if node["rule"] == "VarDecl":
            return VarDeclaration(children[0]["terminal"], children[1]["terminal"], self.ast_from_expression(children[3]))
        if node["rule"] == "Assignment":
            return Assignment(children[0]["terminal"], self.ast_from_expression(children[2]))
        if node["rule"] == "IfStmt":
            else_branch = self.ast_from_block(children[6]) if len(children) == 7 else None
            return IfStatement(self.ast_from_expression(children[2]), self.ast_from_block(children[4]), else_branch)
        raise ParseError(f"Unsupported statement rule {node['rule']!r}")

    def ast_from_block(self, node: dict[str, Any]) -> list[Any]:
        return [self.ast_from_statement(child) for child in node["children"][1:-1]]

    def ast_from_expression(self, node: dict[str, Any]) -> Any:
        if node["rule"] in {"Expression", "Comparison", "Term", "Factor"}:
            result = self.ast_from_expression(node["children"][0])
            for index in range(1, len(node["children"]), 2):
                result = BinaryExpression(node["children"][index]["terminal"], result, self.ast_from_expression(node["children"][index + 1]))
            return result
        children = node["children"]
        if node["rule"] == "Unary":
            return UnaryExpression(children[0]["terminal"], self.ast_from_expression(children[1]))
        if node["rule"] == "Grouping":
            return self.ast_from_expression(children[1])
        if node["rule"] == "Number":
            text = children[0]["terminal"]
            return Literal(float(text) if "." in text else int(text))
        if node["rule"] == "String":
            return Literal(bytes(children[0]["terminal"][1:-1], "utf-8").decode("unicode_escape"))
        if node["rule"] == "Boolean":
            return Literal(children[0]["terminal"] == "true")
        if node["rule"] == "Identifier":
            return Identifier(children[0]["terminal"])
        raise ParseError(f"Unsupported expression rule {node['rule']!r}")


def to_dict(value: Any) -> Any:
    """Convert AST dataclasses and nested values into ordinary dictionaries."""
    if is_dataclass(value):
        return {"type": type(value).__name__, **{field.name: to_dict(getattr(value, field.name)) for field in fields(value)}}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    return value


def parse_source(source: str) -> dict[str, Any]:
    """Validate source and return its concrete parse tree and abstract syntax tree."""
    ast, parse_tree = Parser(tokenize(source)).parse()
    return {"parse_tree": parse_tree, "ast": to_dict(ast)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the mini-language and print its CST and AST.")
    parser.add_argument("source", nargs="?", help="one-line source; omit to read a complete program from stdin")
    parser.add_argument("--ebnf", action="store_true", help="print the predefined grammar and exit")
    args = parser.parse_args()
    if args.ebnf:
        print(EBNF_GRAMMAR, end="")
        return
    source = args.source if args.source is not None else sys.stdin.read()
    if not source.strip():
        parser.error("No source was provided")
    try:
        if args.ebnf:
            print(GRAMMAR)
        print(json.dumps(parse_source(source), indent=2, ensure_ascii=False))
    except ParseError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

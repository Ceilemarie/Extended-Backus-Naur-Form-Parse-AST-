"""A parser for a practical C language subset.

The language intentionally focuses on the syntax used in real C programs:

    Program        = { FunctionDef | Statement | Declaration } ;
    FunctionDef    = Type, Identifier, "(", [ ParameterList ], ")", Block ;
    ParameterList   = Parameter, { ",", Parameter } ;
    Parameter       = Type, [ Identifier ] ;
    Statement      = Block | IfStmt | WhileStmt | ForStmt | ReturnStmt | Declaration | Expression, ";" ;
    IfStmt         = "if", "(", Expression, ")", Statement, [ "else", Statement ] ;
    WhileStmt      = "while", "(", Expression, ")", Statement ;
    ForStmt        = "for", "(", [ Expression | Declaration ], ";", [ Expression ], ";", [ Expression ], ")", Statement ;
    ReturnStmt     = "return", [ Expression ], ";" ;
    Expression     = Assignment ;
    Assignment     = LogicalOr, [ ("=" | "+=" | "-=" | "*=" | "/=" | "%="), Assignment ] ;
    LogicalOr      = LogicalAnd, { "||", LogicalAnd } ;
    LogicalAnd     = Equality, { "&&", Equality } ;
    Equality       = Relational, { ("==" | "!="), Relational } ;
    Relational     = Additive, { ("<" | "<=" | ">" | ">="), Additive } ;
    Additive       = Multiplicative, { ("+" | "-"), Multiplicative } ;
    Multiplicative = Unary, { ("*" | "/" | "%"), Unary } ;
    Unary          = ("+" | "-" | "!" | "~"), Unary | Postfix ;
    Postfix        = Primary, { ("(" , [ ArgumentList ], ")" | "[" , Expression , "]" | "." , Identifier | "->" , Identifier) } ;
    ArgumentList   = Assignment, { ",", Assignment } ;
    Primary        = Number | String | Char | Identifier | "(", Expression, ")" ;

This subset accepts the common patterns used in C programs while keeping the
parser small enough to teach the front-end pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import argparse
import json
import re
import sys
from typing import Any, Iterable, NoReturn


EBNF_GRAMMAR = """\
Program         = { FunctionDef | Declaration | Statement } ;
FunctionDef     = Type, Identifier, "(", [ ParameterList ], ")", Block ;
ParameterList   = Parameter, { ",", Parameter } ;
Parameter       = Type, [ Identifier ] ;
Statement       = Block | IfStmt | WhileStmt | ForStmt | ReturnStmt | Declaration | Expression, ";" ;
IfStmt          = "if", "(", Expression, ")", Statement, [ "else", Statement ] ;
WhileStmt       = "while", "(", Expression, ")", Statement ;
ForStmt         = "for", "(", [ Expression | Declaration ], ";", [ Expression ], ";", [ Expression ], ")", Statement ;
ReturnStmt      = "return", [ Expression ], ";" ;
Expression      = Assignment ;
Assignment      = LogicalOr, [ ("=" | "+=" | "-=" | "*=" | "/=" | "%="), Assignment ] ;
LogicalOr       = LogicalAnd, { "||", LogicalAnd } ;
LogicalAnd      = Equality, { "&&", Equality } ;
Equality        = Relational, { ("==" | "!="), Relational } ;
Relational      = Additive, { ("<" | "<=" | ">" | ">="), Additive } ;
Additive        = Multiplicative, { ("+" | "-"), Multiplicative } ;
Multiplicative  = Unary, { ("*" | "/" | "%"), Unary } ;
Unary           = ("+" | "-" | "!" | "~"), Unary | Postfix ;
Postfix         = Primary, { ("(" , [ ArgumentList ], ")" | "[" , Expression , "]" | "." , Identifier | "->" , Identifier) } ;
ArgumentList    = Assignment, { ",", Assignment } ;
Primary         = Number | String | Char | Identifier | "(", Expression, ")" ;
"""


class ParseError(ValueError):
    """Raised when source text does not match the supported C subset."""


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
class Block:
    statements: list[Any]


@dataclass(frozen=True)
class FunctionDefinition:
    return_type: str
    name: str
    parameters: list[Any]
    body: list[Any]


@dataclass(frozen=True)
class Parameter:
    type_name: str
    name: str | None


@dataclass(frozen=True)
class VarDeclaration:
    type_name: str
    name: str
    initializer: Any | None


@dataclass(frozen=True)
class Assignment:
    name: str
    operator: str
    value: Any


@dataclass(frozen=True)
class IfStatement:
    condition: Any
    then_branch: list[Any]
    else_branch: list[Any] | None


@dataclass(frozen=True)
class WhileStatement:
    condition: Any
    body: list[Any]


@dataclass(frozen=True)
class ForStatement:
    init: Any | None
    condition: Any | None
    update: Any | None
    body: list[Any]


@dataclass(frozen=True)
class ReturnStatement:
    value: Any | None


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
class CallExpression:
    callee: Any
    arguments: list[Any]


@dataclass(frozen=True)
class Literal:
    value: Any


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class PreprocessorDirective:
    directive: str
    value: str | None = None


TYPE_KEYWORDS = {
    "bool",
    "char",
    "const",
    "double",
    "float",
    "int",
    "long",
    "short",
    "signed",
    "unsigned",
    "void",
    "volatile",
}
CONTROL_KEYWORDS = {
    "if",
    "else",
    "for",
    "while",
    "return",
    "break",
    "continue",
    "switch",
    "case",
    "default",
    "sizeof",
}
KEYWORDS = TYPE_KEYWORDS | CONTROL_KEYWORDS | {"true", "false", "NULL"}

TOKEN_RE = re.compile(
    r"""
    (?P<WHITESPACE>[ \t\r]+)
  | (?P<NEWLINE>\n)
  | (?P<COMMENT>//[^\n]*|/\*.*?\*/)
  | (?P<PREPROCESSOR>\#[ \t]*[A-Za-z_][A-Za-z0-9_]*)
  | (?P<HEADER><[^>\n]+>)
  | (?P<NUMBER>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[A-Za-z_]*)
  | (?P<STRING>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
  | (?P<OP>>>=|<<=|==|!=|<=|>=|&&|\|\||->|<<|>>|[+\-*/%<>=!~;:,.(){}\[\]&|^?])
  | (?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE | re.DOTALL,
)

ASSIGNMENT_OPERATORS = {"=", "+=", "-=", "*=", "/=", "%="}


def tokenize(source: str) -> list[Token]:
    """Tokenize the supported C subset and report invalid characters cleanly."""
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
        token_kind = kind
        if kind == "IDENTIFIER" and value in KEYWORDS:
            token_kind = "KEYWORD"
        elif kind == "PREPROCESSOR":
            token_kind = "PREPROCESSOR"
        elif kind == "HEADER":
            token_kind = "HEADER"
        elif kind == "STRING":
            token_kind = "STRING"
        elif kind == "NUMBER":
            token_kind = "NUMBER"
        elif kind == "OP":
            token_kind = "OP"
        if kind not in {"WHITESPACE", "NEWLINE", "COMMENT"}:
            tokens.append(Token(token_kind, value, position, line, column))
        line += value.count("\n")
        column = column + len(value) if "\n" not in value else len(value.rsplit("\n", 1)[-1]) + 1
        position = match.end()
    tokens.append(Token("EOF", "", len(source), line, column))
    return tokens


class Parser:
    """Recursive-descent parser for a practical C subset."""

    def __init__(self, tokens: Iterable[Token]):
        self.tokens = list(tokens)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    @property
    def previous(self) -> Token:
        return self.tokens[self.index - 1]

    def peek(self, offset: int = 1) -> Token:
        index = self.index + offset
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        return token

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
        children: list[dict[str, Any]] = []
        while self.current.kind != "EOF":
            if self.current.kind == "PREPROCESSOR":
                children.append(self.preprocessor_cst())
            else:
                children.append(self.top_level_cst())
        return {"rule": "Program", "children": children}

    def preprocessor_cst(self) -> dict[str, Any]:
        directive = self.leaf(self.advance())
        if self.current.kind == "HEADER":
            children = [directive, self.leaf(self.advance())]
            return {"rule": "PreprocessorDirective", "children": children}
        if self.current.kind == "STRING":
            children = [directive, self.leaf(self.advance())]
            return {"rule": "PreprocessorDirective", "children": children}
        return {"rule": "PreprocessorDirective", "children": [directive]}

    def top_level_cst(self) -> dict[str, Any]:
        if self._starts_type() and self.peek().kind == "IDENTIFIER" and self.peek(2).value == "(":
            return self.function_def_cst()
        if self._starts_type():
            return self.declaration_cst()
        if self.current.value == "if":
            return self.if_cst()
        if self.current.value == "while":
            return self.while_cst()
        if self.current.value == "for":
            return self.for_cst()
        if self.current.value == "return":
            return self.return_cst()
        if self.current.value == "{":
            return self.block_cst()
        return self.expression_statement_cst()

    def _starts_type(self) -> bool:
        if self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS:
            return True
        if self.current.kind == "KEYWORD" and self.current.value in {"const", "volatile", "unsigned", "signed"}:
            return True
        return False

    def function_def_cst(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        while self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS | {"const", "volatile", "unsigned", "signed"}:
            children.append(self.leaf(self.advance()))
        children.append(self.leaf(self.expect_kind("IDENTIFIER")))
        children.append(self.leaf(self.expect("(")))
        parameter_list: list[dict[str, Any]] = []
        if self.current.value != ")":
            parameter_list.append(self.parameter_cst())
            while self.match(","):
                parameter_list.append(self.parameter_cst())
        children.append({"rule": "ParameterList", "children": parameter_list})
        children.append(self.leaf(self.expect(")")))
        children.append(self.block_cst())
        return {"rule": "FunctionDef", "children": children}

    def parameter_cst(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        while self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS | {"const", "volatile", "unsigned", "signed"}:
            children.append(self.leaf(self.advance()))
        if self.current.kind == "IDENTIFIER":
            children.append(self.leaf(self.advance()))
        return {"rule": "Parameter", "children": children}

    def block_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("{"))]
        while self.current.value != "}" and self.current.kind != "EOF":
            if self.current.kind == "PREPROCESSOR":
                children.append(self.preprocessor_cst())
            else:
                children.append(self.statement_cst())
        if self.current.kind == "EOF":
            self.error("Expected '}' to close block")
        children.append(self.leaf(self.expect("}")))
        return {"rule": "Block", "children": children}

    def declaration_cst(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        while self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS | {"const", "volatile", "unsigned", "signed"}:
            children.append(self.leaf(self.advance()))
        children.append(self.leaf(self.expect_kind("IDENTIFIER")))
        while self.match(","):
            children.append(self.leaf(self.previous))
            children.append(self.leaf(self.expect_kind("IDENTIFIER")))
        if self.match("="):
            children.append(self.leaf(self.previous))
            children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(";")))
        return {"rule": "VarDecl", "children": children}

    def statement_cst(self) -> dict[str, Any]:
        if self.current.kind == "PREPROCESSOR":
            return self.preprocessor_cst()
        if self.current.value == "{":
            return self.block_cst()
        if self.current.value == "if":
            return self.if_cst()
        if self.current.value == "while":
            return self.while_cst()
        if self.current.value == "for":
            return self.for_cst()
        if self.current.value == "return":
            return self.return_cst()
        if self._starts_type():
            return self.declaration_cst()
        if self.current.value in {"break", "continue"}:
            keyword = self.leaf(self.advance())
            if self.current.value == ";":
                return {"rule": "ControlStmt", "children": [keyword, self.leaf(self.expect(";"))]}
            return {"rule": "ControlStmt", "children": [keyword]}
        return self.expression_statement_cst()

    def if_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("if")), self.leaf(self.expect("("))]
        children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(")")))
        then_branch = self.statement_cst()
        children.append(then_branch)
        if self.match("else"):
            children.append(self.leaf(self.previous))
            children.append(self.statement_cst())
        return {"rule": "IfStmt", "children": children}

    def while_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("while")), self.leaf(self.expect("("))]
        children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(")")))
        children.append(self.statement_cst())
        return {"rule": "WhileStmt", "children": children}

    def for_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("for")), self.leaf(self.expect("("))]
        if self.current.value != ";":
            if self._starts_type():
                children.append(self.declaration_cst())
            else:
                children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(";")))
        if self.current.value != ";":
            children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(";")))
        if self.current.value != ")":
            children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(")")))
        children.append(self.statement_cst())
        return {"rule": "ForStmt", "children": children}

    def return_cst(self) -> dict[str, Any]:
        children = [self.leaf(self.expect("return"))]
        if self.current.value != ";":
            children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(";")))
        return {"rule": "ReturnStmt", "children": children}

    def expression_statement_cst(self) -> dict[str, Any]:
        expression = self.assignment_cst()
        children = [expression]
        children.append(self.leaf(self.expect(";")))
        return {"rule": "ExpressionStmt", "children": children}

    def assignment_cst(self) -> dict[str, Any]:
        left = self.logical_or_cst()
        if self.current.value in ASSIGNMENT_OPERATORS:
            operator = self.leaf(self.advance())
            right = self.assignment_cst()
            return {"rule": "Assignment", "children": [left, operator, right]}
        return left

    def logical_or_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.logical_and_cst, {"||"}, "LogicalOr")

    def logical_and_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.equality_cst, {"&&"}, "LogicalAnd")

    def equality_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.relational_cst, {"==", "!="}, "Equality")

    def relational_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.additive_cst, {"<", "<=", ">", ">="}, "Relational")

    def additive_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.multiplicative_cst, {"+", "-"}, "Additive")

    def multiplicative_cst(self) -> dict[str, Any]:
        return self.binary_cst(self.unary_cst, {"*", "/", "%"}, "Multiplicative")

    def binary_cst(self, operand: Any, operators: set[str], rule: str) -> dict[str, Any]:
        children = [operand()]
        while self.current.value in operators:
            children.extend([self.leaf(self.advance()), operand()])
        return {"rule": rule, "children": children}

    def unary_cst(self) -> dict[str, Any]:
        if self.current.value in {"+", "-", "!", "~"}:
            operator = self.leaf(self.advance())
            return {"rule": "Unary", "children": [operator, self.unary_cst()]}
        return self.postfix_cst()

    def postfix_cst(self) -> dict[str, Any]:
        node = self.primary_cst()
        while self.current.value in {"(", "[", ".", "->"}:
            if self.current.value == "(":
                self.advance()
                args: list[dict[str, Any]] = []
                if self.current.value != ")":
                    args.append(self.assignment_cst())
                    while self.match(","):
                        args.append(self.assignment_cst())
                self.expect(")")
                node = {"rule": "CallExpression", "children": [node, {"rule": "ArgumentList", "children": args}]}
            elif self.current.value == "[":
                self.advance()
                index_expr = self.assignment_cst()
                self.expect("]")
                node = {"rule": "ArrayAccess", "children": [node, index_expr]}
            elif self.current.value == ".":
                dot = self.leaf(self.advance())
                member = self.leaf(self.expect_kind("IDENTIFIER"))
                node = {"rule": "MemberAccess", "children": [node, dot, member]}
            elif self.current.value == "->":
                operator = self.leaf(self.advance())
                member = self.leaf(self.expect_kind("IDENTIFIER"))
                node = {"rule": "MemberAccess", "children": [node, operator, member]}
        return node

    def primary_cst(self) -> dict[str, Any]:
        if self.match("("):
            opening = self.tokens[self.index - 1]
            expression = self.assignment_cst()
            return {"rule": "Grouping", "children": [self.leaf(opening), expression, self.leaf(self.expect(")"))]}
        if self.current.kind == "NUMBER":
            return {"rule": "Number", "children": [self.leaf(self.advance())]}
        if self.current.kind == "STRING":
            return {"rule": "String", "children": [self.leaf(self.advance())]}
        if self.current.value in {"true", "false"}:
            return {"rule": "Boolean", "children": [self.leaf(self.advance())]}
        if self.current.kind == "IDENTIFIER":
            return {"rule": "Identifier", "children": [self.leaf(self.advance())]}
        self.error("Expected a number, string, identifier, boolean literal, or parenthesized expression")

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
        return Program([self.ast_from_node(child) for child in node["children"]])

    def ast_from_node(self, node: dict[str, Any]) -> Any:
        rule = node["rule"]
        if rule == "FunctionDef":
            return self.ast_from_function(node)
        if rule == "PreprocessorDirective":
            return PreprocessorDirective(node["children"][0]["terminal"], node["children"][1]["terminal"] if len(node["children"]) > 1 else None)
        if rule == "VarDecl":
            name = None
            initializer = None
            type_parts = []
            for child in node["children"]:
                if child.get("kind") == "KEYWORD":
                    type_parts.append(child["terminal"])
                elif child.get("kind") == "IDENTIFIER":
                    if name is None:
                        name = child["terminal"]
            type_name = " ".join(type_parts)
            for idx, child in enumerate(node["children"]):
                if child.get("terminal") == "=":
                    initializer = self.ast_from_expression(node["children"][idx + 1])
                    break
            return VarDeclaration(type_name, name or "", initializer)
        if rule == "Assignment":
            left = self.ast_from_expression(node["children"][0])
            if isinstance(left, Identifier):
                return Assignment(left.name, node["children"][1]["terminal"], self.ast_from_expression(node["children"][2]))
            return Assignment(str(left), node["children"][1]["terminal"], self.ast_from_expression(node["children"][2]))
        if rule == "IfStmt":
            condition = self.ast_from_expression(node["children"][2])
            then_branch = self.ast_from_block(node["children"][4]) if node["children"][4]["rule"] == "Block" else [self.ast_from_node(node["children"][4])]
            else_branch = None
            if len(node["children"]) > 6:
                else_branch = self.ast_from_block(node["children"][6]) if node["children"][6]["rule"] == "Block" else [self.ast_from_node(node["children"][6])]
            return IfStatement(condition, then_branch, else_branch)
        if rule == "WhileStmt":
            return WhileStatement(self.ast_from_expression(node["children"][2]), self.ast_from_block(node["children"][4]))
        if rule == "ForStmt":
            init = None
            condition = None
            update = None
            children = node["children"]
            idx = 2
            if idx < len(children) and children[idx]["rule"] != "Block":
                init = self.ast_from_node(children[idx]) if children[idx]["rule"] == "VarDecl" else self.ast_from_expression(children[idx])
                idx += 1
            if idx < len(children) and children[idx]["terminal"] == ";":
                idx += 1
            if idx < len(children) and children[idx]["rule"] != "Block" and children[idx]["terminal"] != ")":
                condition = self.ast_from_expression(children[idx])
                idx += 1
            if idx < len(children) and children[idx]["terminal"] == ";":
                idx += 1
            if idx < len(children) and children[idx]["rule"] != "Block" and children[idx]["terminal"] != ")":
                update = self.ast_from_expression(children[idx])
                idx += 1
            if idx < len(children) and children[idx]["rule"] == "Block":
                body = self.ast_from_block(children[idx])
            else:
                body = [self.ast_from_node(children[idx])]
            return ForStatement(init, condition, update, body)
        if rule == "ReturnStmt":
            value = None if len(node["children"]) == 2 else self.ast_from_expression(node["children"][1])
            return ReturnStatement(value)
        if rule == "ExpressionStmt":
            return self.ast_from_expression(node["children"][0])
        if rule == "Block":
            return Block([self.ast_from_node(child) for child in node["children"][1:-1]])
        if rule == "ControlStmt":
            return node["children"][0]["terminal"]
        raise ParseError(f"Unsupported AST node rule {rule!r}")

    def ast_from_function(self, node: dict[str, Any]) -> FunctionDefinition:
        parameter_list = node["children"][3]["children"]
        params = [self.ast_from_parameter(parameter) for parameter in parameter_list]
        body = self.ast_from_block(node["children"][5])
        return FunctionDefinition(
            return_type=" ".join(child["terminal"] for child in node["children"][:-5] if child["kind"] in {"KEYWORD"}),
            name=node["children"][1]["terminal"] if len(node["children"]) > 1 else "",
            parameters=params,
            body=body,
        )

    def ast_from_parameter(self, parameter: dict[str, Any]) -> Parameter:
        types = [child["terminal"] for child in parameter["children"] if child.get("kind") == "KEYWORD"]
        name = next((child["terminal"] for child in parameter["children"] if child.get("kind") == "IDENTIFIER"), None)
        return Parameter(" ".join(types), name)

    def ast_from_block(self, node: dict[str, Any]) -> list[Any]:
        if node["rule"] != "Block":
            return [self.ast_from_node(node)]
        return [self.ast_from_node(child) for child in node["children"][1:-1]]

    def ast_from_expression(self, node: dict[str, Any]) -> Any:
        rule = node["rule"]
        if rule in {"Assignment", "Equality", "Relational", "Additive", "Multiplicative", "LogicalAnd", "LogicalOr"}:
            if rule == "Assignment":
                left = self.ast_from_expression(node["children"][0])
                operator = node["children"][1]["terminal"]
                right = self.ast_from_expression(node["children"][2])
                return BinaryExpression(operator, left, right)
            result = self.ast_from_expression(node["children"][0])
            for index in range(1, len(node["children"]), 2):
                result = BinaryExpression(node["children"][index]["terminal"], result, self.ast_from_expression(node["children"][index + 1]))
            return result
        if rule == "Unary":
            return UnaryExpression(node["children"][0]["terminal"], self.ast_from_expression(node["children"][1]))
        if rule == "Grouping":
            return self.ast_from_expression(node["children"][1])
        if rule == "Number":
            text = node["children"][0]["terminal"]
            return Literal(float(text) if "." in text or "e" in text.lower() else int(text))
        if rule == "String":
            return Literal(node["children"][0]["terminal"][1:-1])
        if rule == "Boolean":
            return Literal(node["children"][0]["terminal"] == "true")
        if rule == "Identifier":
            return Identifier(node["children"][0]["terminal"])
        if rule == "CallExpression":
            callee = self.ast_from_expression(node["children"][0])
            args = []
            if len(node["children"]) > 1 and node["children"][1].get("rule") == "ArgumentList":
                args = [self.ast_from_expression(child) for child in node["children"][1]["children"]]
            return CallExpression(callee, args)
        if rule == "MemberAccess":
            target = self.ast_from_expression(node["children"][0])
            member = node["children"][2]["terminal"]
            return BinaryExpression(".", target, Identifier(member))
        if rule == "ArrayAccess":
            target = self.ast_from_expression(node["children"][0])
            index = self.ast_from_expression(node["children"][1])
            return BinaryExpression("[]", target, index)
        raise ParseError(f"Unsupported expression rule {rule!r}")


def to_dict(value: Any) -> Any:
    """Convert dataclasses and nested values into ordinary dictionaries."""
    if is_dataclass(value):
        return {"type": type(value).__name__, **{field.name: to_dict(getattr(value, field.name)) for field in fields(value)}}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [to_dict(item) for item in value]
    return value


def parse_source(source: str) -> dict[str, Any]:
    """Validate source and return the concrete parse tree and AST."""
    ast, parse_tree = Parser(tokenize(source)).parse()
    return {"parse_tree": parse_tree, "ast": to_dict(ast)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a practical C subset and print its CST and AST.")
    parser.add_argument("source", nargs="?", help="source code to parse; omit to read from stdin")
    parser.add_argument("--ebnf", action="store_true", help="print the grammar instead of parsing source")
    args = parser.parse_args()

    if args.ebnf:
        print(EBNF_GRAMMAR, end="")
        return

    source = args.source if args.source is not None else sys.stdin.read()
    if not source.strip():
        parser.error("No source was provided")
    try:
        print(json.dumps(parse_source(source), indent=2, ensure_ascii=False))
    except ParseError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

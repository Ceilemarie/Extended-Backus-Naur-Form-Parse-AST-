"""Parser.


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
    """Conditional statement with an optional then branch and else branch."""
    condition: Any
    then_branch: list[Any]
    else_branch: list[Any] | None


@dataclass(frozen=True)
class WhileStatement:
    """Loop that repeats while the condition remains true."""
    condition: Any
    body: list[Any]


@dataclass(frozen=True)
class ForStatement:
    """Loop with initialization, condition, update, and body."""
    init: Any | None
    condition: Any | None
    update: Any | None
    body: list[Any]


@dataclass(frozen=True)
class ReturnStatement:
    """Statement that returns an optional value from a function."""
    value: Any | None


@dataclass(frozen=True)
class BinaryExpression:
    """Expression with an operator and two operands, such as a + b."""
    operator: str
    left: Any
    right: Any


@dataclass(frozen=True)
class UnaryExpression:
    """Expression with an operator and a single operand, such as -a."""
    operator: str
    operand: Any


@dataclass(frozen=True)
class CallExpression:
    """Function call with a list of arguments."""
    callee: Any
    arguments: list[Any]


@dataclass(frozen=True)
class Literal:
    """Literal value such as a number, string, or boolean."""
    value: Any


@dataclass(frozen=True)
class Identifier:
    """Name of a variable, function, or another identifier."""
    name: str


@dataclass(frozen=True)
class PreprocessorDirective:
    """C preprocessor directive such as #include or #define."""
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
    """Split the source into tokens and report invalid characters clearly."""
    # Store all tokens recognized from the source here.
    tokens: list[Token] = []
    # Position, line, and column are used to pinpoint the error location.
    position = 0
    line = 1
    column = 1
    # Continue until the entire source string has been processed.
    while position < len(source):
        # Try to match the regular expression at the current position.
        match = TOKEN_RE.match(source, position)
        if match is None:
            # If no match is found, an unsupported character is present.
            char = source[position]
            raise ParseError(f"Unexpected character {char!r} at line {line}, column {column}")
        # Retrieve the regex group name and the text that matched.
        kind = match.lastgroup
        value = match.group()
        token_kind = kind
        # Treat identifiers that are in the keyword list as KEYWORD tokens.
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
            # Whitespace and comments are excluded from the token stream.
            tokens.append(Token(token_kind, value, position, line, column))
        # Update the line and column for the next token.
        line += value.count("\n")
        column = column + len(value) if "\n" not in value else len(value.rsplit("\n", 1)[-1]) + 1
        position = match.end()
    # The EOF token clearly marks the end of the input.
    tokens.append(Token("EOF", "", len(source), line, column))
    return tokens


class Parser:
    """Practical recursive-descent parser for a C subset."""

    def __init__(self, tokens: Iterable[Token]):
        """Prepare the token list and point the index to the first token."""
        self.tokens = list(tokens)
        self.index = 0

    @property
    def current(self) -> Token:
        """Return the token currently being examined."""
        return self.tokens[self.index]

    @property
    def previous(self) -> Token:
        """Return the token before the current one."""
        return self.tokens[self.index - 1]

    def peek(self, offset: int = 1) -> Token:
        """Look ahead at the next token without moving the index."""
        index = self.index + offset
        if index >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[index]

    def advance(self) -> Token:
        """Consume the current token and move to the next one."""
        token = self.current
        if token.kind != "EOF":
            self.index += 1
        return token

    def match(self, *values: str) -> bool:
        """If the value matches, consume the token and return True."""
        if self.current.value in values:
            self.advance()
            return True
        return False

    def expect(self, value: str) -> Token:
        """Require an exact token value; raise an error if it does not match."""
        if self.current.value != value:
            raise ParseError(f"Expected {value!r}, found {self.current.value or 'end of input'} at position {self.current.position}")
        return self.advance()

    def expect_kind(self, kind: str) -> Token:
        """Require a token by its kind rather than by its literal text."""
        if self.current.kind != kind:
            raise ParseError(f"Expected {kind}, found {self.current.value or 'end of input'} at position {self.current.position}")
        return self.advance()

    def error(self, message: str) -> NoReturn:
        """Raise a ParseError using the current token location."""
        token = self.current
        raise ParseError(f"{message} at line {token.line}, column {token.column}")

    def parse(self) -> tuple[Program, dict[str, Any]]:
        """Build the CST and then convert it to an AST."""
        tree = self.program_cst()
        return self.ast_from_program(tree), tree

    def program_cst(self) -> dict[str, Any]:
        """Parse the entire program as the root Program CST node."""
        children: list[dict[str, Any]] = []
        while self.current.kind != "EOF":
            # The preprocessor is handled separately from normal top-level statements.
            if self.current.kind == "PREPROCESSOR":
                children.append(self.preprocessor_cst())
            else:
                children.append(self.top_level_cst())
        return {"rule": "Program", "children": children}

    def preprocessor_cst(self) -> dict[str, Any]:
        """Parse a #include/#define-style directive and its optional value."""
        directive = self.leaf(self.advance())
        if self.current.kind == "HEADER":
            children = [directive, self.leaf(self.advance())]
            return {"rule": "PreprocessorDirective", "children": children}
        if self.current.kind == "STRING":
            children = [directive, self.leaf(self.advance())]
            return {"rule": "PreprocessorDirective", "children": children}
        return {"rule": "PreprocessorDirective", "children": [directive]}

    def top_level_cst(self) -> dict[str, Any]:
        """Select the correct parser for a top-level construct."""
        # Type + name + '(' is recognized as a function definition.
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
        """Check whether the current token can begin a type."""
        if self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS:
            return True
        if self.current.kind == "KEYWORD" and self.current.value in {"const", "volatile", "unsigned", "signed"}:
            return True
        return False

    def function_def_cst(self) -> dict[str, Any]:
        """Parse the return type, name, parameters, and function body."""
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
        """Parse the type and optional name of a parameter."""
        children: list[dict[str, Any]] = []
        while self.current.kind == "KEYWORD" and self.current.value in TYPE_KEYWORDS | {"const", "volatile", "unsigned", "signed"}:
            children.append(self.leaf(self.advance()))
        if self.current.kind == "IDENTIFIER":
            children.append(self.leaf(self.advance()))
        return {"rule": "Parameter", "children": children}

    def block_cst(self) -> dict[str, Any]:
        """Parse the statements inside { ... }."""
        children = [self.leaf(self.expect("{"))]
        while self.current.value != "}" and self.current.kind != "EOF":
            # This also accepts preprocessor directives inside a block.
            if self.current.kind == "PREPROCESSOR":
                children.append(self.preprocessor_cst())
            else:
                children.append(self.statement_cst())
        if self.current.kind == "EOF":
            self.error("Expected '}' to close block")
        children.append(self.leaf(self.expect("}")))
        return {"rule": "Block", "children": children}

    def declaration_cst(self) -> dict[str, Any]:
        """Parse the variable declaration, initializer, and semicolon."""
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
        """Identify the type of statement represented by the current token."""
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
        """Parse the if condition, then branch, and optional else branch."""
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
        """Parse the while condition and the repeated statement."""
        children = [self.leaf(self.expect("while")), self.leaf(self.expect("("))]
        children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(")")))
        children.append(self.statement_cst())
        return {"rule": "WhileStmt", "children": children}

    def for_cst(self) -> dict[str, Any]:
        """Parse the three parts of the for loop and its body."""
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
        """Parse the return statement and its optional expression before the semicolon."""
        children = [self.leaf(self.expect("return"))]
        if self.current.value != ";":
            children.append(self.assignment_cst())
        children.append(self.leaf(self.expect(";")))
        return {"rule": "ReturnStmt", "children": children}

    def expression_statement_cst(self) -> dict[str, Any]:
        """Parse an expression that ends with a semicolon."""
        expression = self.assignment_cst()
        children = [expression]
        children.append(self.leaf(self.expect(";")))
        return {"rule": "ExpressionStmt", "children": children}

    def assignment_cst(self) -> dict[str, Any]:
        """Parse the assignment; it is right-associative for cases like a = b = 1."""
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
        """Generic helper for binary operators that share the same precedence."""
        children = [operand()]
        while self.current.value in operators:
            children.extend([self.leaf(self.advance()), operand()])
        return {"rule": rule, "children": children}

    def unary_cst(self) -> dict[str, Any]:
        """Parse the unary operator or higher-precedence postfix expression."""
        if self.current.value in {"+", "-", "!", "~"}:
            operator = self.leaf(self.advance())
            return {"rule": "Unary", "children": [operator, self.unary_cst()]}
        return self.postfix_cst()

    def postfix_cst(self) -> dict[str, Any]:
        """Parse calls, array access, and member access after the primary expression."""
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
        """Parse the most basic expression, such as a literal or identifier."""
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
        """Convert a token into a CST leaf dictionary along with its location."""
        return {
            "terminal": token.value,
            "kind": token.kind,
            "position": token.position,
            "line": token.line,
            "column": token.column,
        }

    def ast_from_program(self, node: dict[str, Any]) -> Program:
        """Convert each child of the Program CST into an AST object."""
        return Program([self.ast_from_node(child) for child in node["children"]])

    def ast_from_node(self, node: dict[str, Any]) -> Any:
        """Dispatch the generic CST node to the correct AST conversion."""
        rule = node["rule"]
        if rule == "FunctionDef":
            return self.ast_from_function(node)
        if rule == "PreprocessorDirective":
            return PreprocessorDirective(node["children"][0]["terminal"], node["children"][1]["terminal"] if len(node["children"]) > 1 else None)
        if rule == "VarDecl":
            # First find the name, type keywords, and initializer.
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
            # The idx variable tracks init, condition, update, and body.
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
            if idx < len(children) and children[idx].get("terminal") == ")":
                idx += 1
            if idx < len(children) and children[idx]["rule"] == "Block":
                body = self.ast_from_block(children[idx])
            elif idx < len(children):
                body = [self.ast_from_node(children[idx])]
            else:
                body = []
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
        """Convert the FunctionDef CST into a FunctionDefinition AST."""
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
        """Convert the Parameter CST into a Parameter AST."""
        types = [child["terminal"] for child in parameter["children"] if child.get("kind") == "KEYWORD"]
        name = next((child["terminal"] for child in parameter["children"] if child.get("kind") == "IDENTIFIER"), None)
        return Parameter(" ".join(types), name)

    def ast_from_block(self, node: dict[str, Any]) -> list[Any]:
        """Return the AST list of statements in a block."""
        if node["rule"] != "Block":
            return [self.ast_from_node(node)]
        return [self.ast_from_node(child) for child in node["children"][1:-1]]

    def ast_from_expression(self, node: dict[str, Any]) -> Any:
        """Convert the expression CST according to its precedence rule."""
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
    """Validate the source and return the CST and AST in JSON-friendly format."""
    ast, parse_tree = Parser(tokenize(source)).parse()
    return {"parse_tree": parse_tree, "ast": to_dict(ast)}


def main() -> None:
    """Entry point of the command-line program."""
    # Build the CLI parser for the source argument and --ebnf option.
    parser = argparse.ArgumentParser(description="Parse a practical C subset and print its CST and AST.")
    parser.add_argument("source", nargs="?", help="source code to parse; omit to read from stdin")
    parser.add_argument("--ebnf", action="store_true", help="print the grammar instead of parsing source")
    args = parser.parse_args()

    if args.ebnf:
        # When --ebnf is used, only the grammar is printed instead of parsing the source.
        print(EBNF_GRAMMAR, end="")
        return

    # Use the positional argument; if it is missing, read from stdin.
    source = args.source if args.source is not None else sys.stdin.read()
    if not source.strip():
        parser.error("No source was provided")
    try:
        # Parse the source and print the result as nicely formatted JSON.
        print(json.dumps(parse_source(source), indent=2, ensure_ascii=False))
    except ParseError as error:
        # Convert the parser error into a clear CLI error message.
        parser.error(str(error))


if __name__ == "__main__":
    # Run the CLI only when the file is executed directly.
    main()

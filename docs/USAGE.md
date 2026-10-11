# Usage and Function Reference

This project has two interfaces:

1. A browser workspace for interactive token, CST, AST, and EBNF output.
2. A dependency-free Python parser for scripts, experiments, and tests.

The parser accepts a practical C subset, not arbitrary C. It supports function
definitions, declarations, assignments, expressions, blocks, `if`, `while`,
`for`, `return`, calls, member/index access, comments, and common
preprocessor directives such as `#include`.

## Browser usage

Start a local server from the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000> and click **Start**.

The workspace then:

1. Tokenizes the source as it is typed.
2. Displays each token and its EBNF terminal category.
3. Parses valid C source into a concrete syntax tree.
4. Builds an abstract syntax tree from the same parse.
5. Generates Mermaid diagrams for the CST and AST.
6. Shows the input-specific EBNF grammar.

Use **Ctrl+Enter** (or **Cmd+Enter** on macOS) to analyze immediately. The
workspace also analyzes input shortly after editing.

### Browser functions

These functions are intentionally scoped inside `script.js`; they are not
exported as a JavaScript module.

| Function | Purpose |
| --- | --- |
| `tokenize(code)` | Scans C source into token objects with `lexeme`, `type`, and `ebnf` fields. |
| `parseCSource(code, tokens)` | Parses the browser token stream and returns `{ parseTree, ast }`. |
| `parseSource(code, tokens)` | Adapter used by the UI to invoke the C parser. |
| `renderTokens(tokens)` | Rebuilds the token table in the workspace. |
| `renderTrees(code, tokens)` | Validates input, updates grammar status, and renders CST/AST diagrams. |
| `buildInputGrammar(parseTree)` | Creates the displayed EBNF text from the current parse tree. |
| `renderMermaidTree(container, value, mode)` | Renders a CST or AST value into a Mermaid diagram. |

## Python CLI usage

Parse a complete C program passed as one argument:

```bash
python3 ebnf_parser_ast.py 'int main(void) { return 0; }'
```

Parse a multi-line program from standard input:

```bash
cat <<'C' | python3 ebnf_parser_ast.py
#include <stdio.h>

int main(void) {
    printf("hello\n");
    return 0;
}
C
```

Print the grammar without parsing source:

```bash
python3 ebnf_parser_ast.py --ebnf
```

The CLI prints JSON containing:

```json
{
  "parse_tree": {},
  "ast": {}
}
```

Invalid input exits with a non-zero status and reports the source location.

## Python API

```python
from ebnf_parser_ast import ParseError, parse_source, tokenize

source = """
#include <stdio.h>

int add(int left, int right) {
    return left + right;
}

int main(void) {
    return add(2, 3);
}
"""

try:
    tokens = tokenize(source)
    result = parse_source(source)
except ParseError as error:
    print(f"Invalid C source: {error}")
else:
    print(tokens)
    print(result["parse_tree"])
    print(result["ast"])
```

### Public Python functions and types

| API | Returns | Description |
| --- | --- | --- |
| `tokenize(source)` | `list[Token]` | Lexes source and records token kind, value, position, line, and column. |
| `parse_source(source)` | `dict[str, Any]` | Validates source and returns JSON-serializable `parse_tree` and `ast` values. |
| `Parser(tokens).parse()` | `tuple[Program, dict]` | Returns the typed dataclass AST and concrete parse tree. |
| `to_dict(value)` | JSON-compatible value | Converts parser dataclasses and nested lists into dictionaries. |
| `ParseError` | exception | Raised for invalid characters or syntax. |
| `EBNF_GRAMMAR` | `str` | The grammar printed by `--ebnf`. |

The `Token` objects returned by `tokenize` contain:

```python
Token(
    kind="KEYWORD",
    value="int",
    position=0,
    line=1,
    column=1,
)
```

## AST node examples

For:

```c
int main(void) { return add(2, 3); }
```

the AST includes nodes shaped like:

```json
{
  "type": "Program",
  "statements": [
    {
      "type": "FunctionDefinition",
      "return_type": "int",
      "name": "main",
      "parameters": [],
      "body": [
        {
          "type": "ReturnStatement",
          "value": {
            "type": "CallExpression",
            "callee": { "type": "Identifier", "name": "add" },
            "arguments": [
              { "type": "Literal", "value": 2 },
              { "type": "Literal", "value": 3 }
            ]
          }
        }
      }
    }
  ]
}
```

## Scope

This is a front-end learning parser. It does not compile or execute C, perform
type checking, or implement every C feature. Unsupported syntax is reported
instead of being silently accepted.

# Code TLDRs

## Architecture in one minute

```text
C source
  -> lexer/tokenizer
  -> token table
  -> recursive-descent parser
  -> concrete syntax tree (CST)
  -> AST conversion
  -> Mermaid diagrams + generated EBNF
```

The project has a static browser front end and a parallel dependency-free
Python implementation of the parser.

## File-by-file TLDR

### `index.html`

Defines the page structure:

- animated landing page
- Start/back navigation
- C source textarea and presets
- CST and AST output panels
- generated EBNF panel
- token table

It contains no parser logic; behavior is wired in `script.js`.

### `styles.css`

Owns presentation only:

- dark/light themes
- landing page and workspace layout
- responsive behavior
- buttons, cards, tables, status messages, and tree panels

### `script.js`

The browser application controller.

Main responsibilities:

- animate the particle background
- switch between landing page and workspace
- persist the selected theme
- tokenize C source
- parse the browser token stream
- convert CST nodes into AST nodes
- generate input-specific EBNF
- render CST and AST diagrams with Mermaid
- show syntax errors without producing a false success state

Important browser parser layers:

```text
parsePrimary
  -> parsePostfix
  -> parseUnary
  -> parseMultiplicative
  -> parseAdditive
  -> parseRelational
  -> parseEquality
  -> parseLogicalAnd
  -> parseLogicalOr
  -> parseAssignment
```

This ordering implements C expression precedence.

### `ebnf_parser_ast.py`

The standalone Python implementation.

Key sections:

- `TOKEN_RE`, keyword sets, and `tokenize`: lexical analysis
- `Parser.program_cst`: complete program parsing
- `Parser.function_def_cst`: function definitions and parameters
- `Parser.statement_cst`: declarations, blocks, control flow, and returns
- `Parser.expression_cst`: operator-precedence expression parsing
- `Parser.ast_from_*`: conversion from CST dictionaries to typed dataclasses
- `parse_source`: public JSON-friendly API
- `main`: command-line interface

The Python parser is useful when the parser should run without a browser or
third-party dependencies.

### `mermaid.min.js`

Vendored Mermaid runtime used to draw the CST and AST diagrams in the browser.
It is a generated third-party asset; application code calls its public
`mermaid.initialize` and `mermaid.render` APIs.

### `ascii.jsx`

Reusable React-style version of the particle/sand animation. It is separate
from the static parser workspace and does not define the C grammar.

### `liminal-stack.png`

Source image sampled by the canvas particle animation.

### `lain.jpg`

Browser favicon used by the landing page.

### `README.md`

Project overview, supported C grammar, repository map, and quick-start
information. The detailed reference material lives in:

- [`docs/USAGE.md`](./USAGE.md)
- [`docs/CODE-TLDRS.md`](./CODE-TLDRS.md)

## Data shape

Browser CST nodes use:

```js
{
  rule: "FunctionDef",
  children: [
    { terminal: "int", kind: "Keyword" }
  ]
}
```

Browser AST nodes use semantic fields:

```js
{
  type: "FunctionDefinition",
  returnType: "int",
  name: "main",
  parameters: [],
  body: []
}
```

Python CST leaves additionally include source position metadata:

```python
{
    "terminal": "int",
    "kind": "KEYWORD",
    "position": 0,
    "line": 1,
    "column": 1,
}
```

## Extension points

To add syntax consistently:

1. Add or update token patterns and keyword sets.
2. Add a parser production at the correct precedence or statement layer.
3. Add the matching AST conversion.
4. Update the browser parser and Python parser together.
5. Add a preset or usage example when the syntax is user-facing.
6. Update the EBNF in `EBNF_GRAMMAR`, the browser grammar builder, and the docs.
7. Run representative valid and invalid C examples through both interfaces.

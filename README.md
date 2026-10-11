# Extended Backus–Naur Form Parse & AST Demo

This project is an interactive educational web app that demonstrates the basics of EBNF (Extended Backus–Naur Form), lexical analysis, and the difference between a concrete parse tree and an abstract syntax tree (AST). It is designed as a visual learning tool for beginners exploring formal grammar and parser concepts, using Python as the only supported language.

The app presents a dark cyberpunk-style landing page, a sand-particle background animation, and a second workspace panel where users can enter source code or upload a file and inspect its tokens, concrete parse tree, and AST.

---

## What this project does

The repository combines:

- a styled landing page and theme toggle
- a particle-based animated background
- a lexer/tokenizer for the teaching language
- a grammar table showing token classes and matching EBNF terminals
- an explicit generated EBNF panel for the supported Python subset
- an in-browser recursive-descent parser
- concrete parse tree and AST visualization
- meaningful syntax errors for invalid statements and blocks
- a learning interface for EBNF, parse tree, and AST concepts
- a Python terminology glossary with 20+ terms

In short, it teaches how source code is broken down into meaningful pieces before it is parsed into a tree structure.

---

## Core concept

The app accepts Python source exclusively. Its browser parser generates a
concrete parse tree and an abstract syntax tree from typed or uploaded source.

The flow is:

1. A user types or selects example code.
2. The code is scanned character by character.
3. Keywords, identifiers, operators, literals, and delimiters are classified into tokens.
4. Each token is displayed in a table with its lexeme, token class, and corresponding EBNF terminal.
5. The interface renders the concrete parse tree and AST alongside the tokens.

This mirrors the real pipeline of compiler and interpreter design:

Source code -> Lexer/Tokenizer -> Parse Tree -> AST -> Execution / Evaluation

---

## Features

### 1. Hero landing page
The home screen shows a large title:

- Extended Backus–Naur Form
- With Parse & AST Tree

It includes:

- a centered start button
- a restore button for the animated background
- a light/dark mode toggle
- a particle canvas background that behaves like a sand simulation

### 2. Sand animation background
The background is rendered with a canvas that creates a sand-like particle effect. The animation responds to mouse movement and click/drag interaction, creating a reactive visual element behind the main interface.

This effect is implemented in both:

- script.js for the static site
- ascii.jsx as a reusable React component version

### 3. Workspace learning panel
After clicking Start, the app transitions to a learning workspace with:

- theory cards explaining EBNF, concrete parse trees, and ASTs
- a multiline source-code console input area
- preset buttons for statement and conditional examples
- a source-file upload control
- automatic AST-to-JSON tree visualization
- a token table that updates live

### 4. Tokenizer / lexer
The app contains a tokenizer that recognizes:

- declaration and conditional keywords such as `let`, `const`, `var`, `if`, and `else`
- identifiers
- number and string literals
- Python operators and delimiters
- indentation, dedentation, newlines, and comments

Each token is displayed with:

- index
- lexeme
- token class
- corresponding EBNF rule label

### 5. EBNF examples and educational layout
The UI is built to teach grammar concepts rather than just process code. It includes text describing:

- what EBNF is
- how concrete parse trees record exact syntax
- how ASTs simplify syntax into semantic structure

---

## Teaching-language syntax modeled by the app

The browser workspace is designed around:

- variable declarations
- assignments
- conditionals
- loops and function calls

Example inputs include:

- `total = 10 + 5`
- `if score >= 75:`
- `    passed = True`
- `for number in range(3):`
- `    print(number)`

The predefined EBNF grammar is:

```
Module         = { Statement } ;
Statement      = Assignment | FunctionDef | IfStmt | ForStmt | WhileStmt | ReturnStmt | ExprStmt ;
Assignment     = Identifier, ("=" | "+=" | "-="), Expr, NEWLINE ;
FunctionDef    = "def", Identifier, "(", [ Parameters ], ")", ":", Suite ;
IfStmt         = "if", Expr, ":", Suite, { "elif", Expr, ":", Suite }, [ "else", ":", Suite ] ;
Suite          = NEWLINE, INDENT, { Statement }, DEDENT ;
Expr           = Python expression ;
```

This helps students connect the formal grammar to the tokens they see in the table.

---

## Repository structure

```text
.
├── index.html          # Main page structure and workspace layout
├── styles.css          # UI styling, dark/light theme, layout, table styles
├── script.js           # Canvas animation, theme logic, lexer/tokenizer, UI behavior
├── ascii.jsx           # React component variant of the sand/particle animation
├── ebnf_parser_ast.py  # Uploadable parser, concrete parse tree, and AST demo
├── liminal-stack.png   # Background image used by the canvas effect
├── README.md           # Project documentation
```

---

## File-by-file overview

### index.html
Defines the full HTML structure for the app, including:

- the intro page
- the start button
- the workspace section
- the grammar/token table
- the input console and preset buttons

### styles.css
Controls the look and feel of the app:

- full-screen intro layout
- dark cyberpunk theme
- light mode toggle styling
- panel layouts
- token badges and table formatting
- responsive layout behavior

### script.js
Contains the functional logic for:

- canvas background animation
- mouse-driven particle effects
- page transitions
- theme persistence with localStorage
- code input handling
- tokenization
- recursive-descent parsing with operator precedence
- live rendering of the token table, concrete parse tree, and AST

### ascii.jsx
This is a React version of the sand particle effect. It is essentially a componentized version of the same visual concept, with a canvas-driven image extraction and particle motion system.

### ebnf_parser_ast.py
This is a dependency-free Python implementation of the documented grammar. It
provides `tokenize`, recursive-descent parsing, a concrete parse tree, and an
AST. The file is self-contained and can be uploaded as a single Python file.

Run it with one statement:

```bash
python3 ebnf_parser_ast.py 'total = 10 + 5'
```

Or pipe a complete block of statements through standard input:

```bash
printf 'for number in range(3):\n    print(number)\n' | python3 ebnf_parser_ast.py
```

The JSON output contains `parse_tree` (including terminals and punctuation)
and `ast` (the simplified semantic structure). Invalid syntax raises a
`ParseError` and the command-line interface reports the source position.

#### Python API

The uploadable Python file exposes these functions and types:

```python
from ebnf_parser_ast import ParseError, parse_source, tokenize

tokens = tokenize("let total = 10 + 5;")
result = parse_source("let total = 10 + 5;")

print(result["parse_tree"])  # Concrete syntax tree
print(result["ast"])         # JSON-serializable AST
```

- `tokenize(source)` returns a list of `Token` objects with line and column information.
- `parse_source(source)` returns a dictionary with `parse_tree` and `ast`.
- `ParseError` identifies invalid syntax and includes the source position.
- `Parser(tokens).parse()` returns the typed `Program` AST and concrete tree
  for callers that need the dataclass representation.

The browser implementation exposes the equivalent behavior through the Run
button, presets, and file upload control. Its internal functions are
`tokenize`, `parsePythonSource`, `renderTokens`, and `renderTrees`; they are
intentionally scoped to the page rather than exported as a module.

### AST JSON tree

After valid teaching-language source is analyzed,
the AST is automatically rendered in a separate visual JSON tree container with
connected Mermaid nodes and branches. The diagram is generated from the AST
after each successful analysis. Invalid source shows
the parse error in the original CST/AST panels and does not generate a JSON
tree.

---

## How the tokenizer works

The tokenizer in script.js scans input left to right and classifies
characters into structured token types.

Examples:

- indentation produces `INDENT` and `DEDENT` tokens
- delimiters and operators are tokenized individually
- numeric sequences become `NumberLiteral` tokens
- quoted text becomes `StringLiteral` tokens
- alphabetic sequences become either keywords or identifiers
- comments and line endings are preserved as tokens
- unrecognized characters are marked as `Unknown`

Each token includes a human-readable EBNF label, and valid input is parsed into
the concrete parse tree and AST panels.

The browser parser accepts declarations, assignments, conditionals, literals,
operators, blocks, and comments. Unknown characters and malformed statements
are reported as parse errors. It is a structural learning parser, not a
general-purpose programming language implementation.

---

## Current limitation

This repo is intentionally a learning/demo project rather than a production
parser. The browser parser validates common Python structure and reports
unsupported characters, but it does not implement every Python grammar rule,
advanced error recovery, or execution. There is no artificial token or
statement limit; practical limits are browser memory and processing time. The
rendered tree panels are scrollable and capped visually at 360px.

The practical milestones represented here are:

- basic UI and visual presentation
- EBNF explanation layer
- tokenization and grammar mapping
- concrete parse tree generation
- AST construction and visualization

The parser uses recursive descent with operator precedence and reports useful
syntax errors, while keeping the implementation small enough for teaching.

---

## Running the project locally

Since this is a static front-end app, you can run it in two easy ways.

### Option 1: Open directly
Open index.html in a browser.

### Option 2: Use a local web server
From the project folder, run:

```bash
python3 -m http.server 8000
```

Then visit:

```text
http://localhost:8000
```

This is usually the most reliable method for local development because it avoids any browser restrictions around loading local assets.

---

## Intended educational purpose

This repository is best understood as a visual teaching tool for:

- formal grammar
- parsing concepts
- lexical analysis
- compiler construction fundamentals
- EBNF syntax notation

It offers a friendly, interactive way to visualize how programming languages break down into meaningful units before they become executable logic.

---

## Summary

The repo is a compact interactive app for learning EBNF and parsing fundamentals. It combines a polished user interface with a lexer, recursive-descent parser, concrete parse tree, and AST demonstration to help users see how source code is transformed into structured representations.

It is a beginner-friendly reference implementation for understanding the front end of language processing, without yet attempting to build a complete compiler or full parser.

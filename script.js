window.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("sandCanvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.src = "liminal-stack.png"; // image used

  let particles = [];
  const mouse = { x: -1000, y: -1000, isDown: false, radius: 55 };

  class Particle {
    constructor(x, y, color) {
      this.originX = x;
      this.originY = y;
      this.x = x;
      this.y = y;
      this.vx = (Math.random() - 0.5) * 2;
      this.vy = (Math.random() - 0.5) * 2;
      this.color = color;
      this.isFalling = false;
    }

    update(width, height) {
      const dx = mouse.x - this.x;
      const dy = mouse.y - this.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      const triggerRadius = mouse.isDown ? mouse.radius * 2 : mouse.radius;
      if (dist < triggerRadius) {
        this.isFalling = true;
        const force = (triggerRadius - dist) / triggerRadius;
        const angle = Math.atan2(dy, dx);
        this.vx -= Math.cos(angle) * force * 6;
        this.vy -= Math.sin(angle) * force * 6;
      }

      if (this.isFalling) {
        this.vy += 0.25; // gravity
        this.vx *= 0.94; // air drag
        this.vy *= 0.94;

        this.x += this.vx;
        this.y += this.vy;

        // Ground floor
        if (this.y >= height - 2) {
          this.y = height - 2;
          this.vy = 0;
          this.vx *= 0.5;
        }

        // Screen borders
        if (this.x < 0) this.x = 0;
        if (this.x > width) this.x = width;
      }
    }

    draw(context) {
      const isLightTheme = document.body.classList.contains("theme-light");
      context.fillStyle = isLightTheme ? "#2563eb" : this.color;
      context.fillRect(Math.round(this.x), Math.round(this.y), 2, 2);
    }

    reset() {
      this.x = this.originX;
      this.y = this.originY;
      this.vx = 0;
      this.vy = 0;
      this.isFalling = false;
    }
  }

  function resizeAndInit() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    if (!img.complete || img.naturalWidth === 0) return;

    particles = [];

    // size of the image
    const targetW = Math.min(550, window.innerWidth * 0.65);
    const targetH = targetW * (img.height / img.width);

    // center the image
    const startX = (canvas.width - targetW) / 2;
    const startY = (canvas.height - targetH) / 2 + 60; // bottom

    const offscreen = document.createElement("canvas");
    const offCtx = offscreen.getContext("2d");
    offscreen.width = targetW;
    offscreen.height = targetH;
    offCtx.drawImage(img, 0, 0, targetW, targetH);

    const imgData = offCtx.getImageData(0, 0, targetW, targetH).data;
    const step = 2; // Density ng dots

    for (let y = 0; y < targetH; y += step) {
      for (let x = 0; x < targetW; x += step) {
        const idx = (y * targetW + x) * 4;
        const r = imgData[idx];
        const alpha = imgData[idx + 3];

        if (alpha > 120 && r < 120) {
          // Positron mint/cyan palette
          particles.push(new Particle(startX + x, startY + y, "#00ffc8"));
        }
      }
    }
  }

  img.onload = () => {
    resizeAndInit();
    animate();
  };

  window.addEventListener("resize", () => {
    resizeAndInit();
  });

  function animate() {
    const isLightTheme = document.body.classList.contains("theme-light");
    ctx.fillStyle = isLightTheme ? "rgba(245, 245, 245, 0.4)" : "rgba(0, 0, 0, 0.4)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < particles.length; i++) {
      particles[i].update(canvas.width, canvas.height);
      particles[i].draw(ctx);
    }

    requestAnimationFrame(animate);
  }

  // Mouse Interaction kahit nasa window level
  window.addEventListener("mousemove", (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });

  window.addEventListener("mousedown", () => (mouse.isDown = true));
  window.addEventListener("mouseup", () => (mouse.isDown = false));
  window.addEventListener("mouseleave", () => {
    mouse.x = -1000;
    mouse.y = -1000;
    mouse.isDown = false;
  });

  // Restore Button Action
  const resetBtn = document.getElementById("resetBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      particles.forEach((p) => p.reset());
    });
  }

});

// --- 2. PAGE TRANSITIONS (START & BACK) ---
  const startBtn = document.getElementById("startBtn");
  const heroSection = document.getElementById("heroSection");
  const workspaceSection = document.getElementById("workspaceSection");
  const backToHeroBtn = document.getElementById("backToHeroBtn");

  startBtn.addEventListener("click", () => {
    heroSection.style.display = "none";
    workspaceSection.classList.remove("hidden");
    document.body.classList.add("workspace-active");
    window.scrollTo({ top: 0, behavior: "smooth" });
    runLexer(); // Run initial tokenize
  });

  backToHeroBtn.addEventListener("click", () => {
    workspaceSection.classList.add("hidden");
    heroSection.style.display = "flex";
    document.body.classList.remove("workspace-active");
  });

  // Theme toggle: dark mode is the default.
  const themeToggleBtns = document.querySelectorAll(".theme-toggle");
  const savedTheme = localStorage.getItem("ebnf-theme");

  if (savedTheme === "light") {
    document.body.classList.add("theme-light");
  }

  function updateThemeToggleLabels() {
    const isLight = document.body.classList.contains("theme-light");
    themeToggleBtns.forEach((button) => {
      button.textContent = isLight ? "Dark mode" : "Light mode";
      button.setAttribute("aria-label", isLight ? "Switch to dark mode" : "Switch to light mode");
    });
  }

  themeToggleBtns.forEach((button) => {
    button.addEventListener("click", () => {
      const isLight = document.body.classList.toggle("theme-light");
      localStorage.setItem("ebnf-theme", isLight ? "light" : "dark");
      updateThemeToggleLabels();
    });
  });

  updateThemeToggleLabels();

  // --- 3. TEACHING-LANGUAGE LEXER / PARSER CORE ---
  const codeInput = document.getElementById("codeInput");
  const runBtn = document.getElementById("runBtn");
  const tokenTableBody = document.getElementById("tokenTableBody");
  const tokenCountBadge = document.getElementById("tokenCountBadge");
  const presetBtns = document.querySelectorAll(".preset-btn");
  const parseTreeTitle = document.getElementById("parseTreeTitle");
  const astTitle = document.getElementById("astTitle");
  const parseTreeOutput = document.getElementById("parseTreeOutput");
  const astOutput = document.getElementById("astOutput");
  const ebnfOutput = document.getElementById("ebnfOutput");
  const grammarStatus = document.getElementById("grammarStatus");

  const KEYWORDS = new Set([
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "False", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not",
    "or", "pass", "raise", "return", "True", "try", "while", "with", "yield",
    "int", "float", "void", "bool", "true", "false",
  ]);
  const OPERATORS = ["**", "//", "->", ":=", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "=>", "+", "-", "*", "/", "%", "=", "<", ">", "|", "&", "^", "~"];
  const DELIMITERS = new Set(["(", ")", "[", "]", "{", "}", ",", ":", ".", ";"]);

  function tokenize(code) {
    const tokens = [];
    const lines = code.replace(/\r\n?/g, "\n").split("\n");
    const indentStack = [0];
    lines.forEach((line, lineIndex) => {
      const leading = line.match(/^[ \t]*/)[0].replace(/\t/g, "    ").length;
      const content = line.slice(line.match(/^[ \t]*/)[0].length);
      if (!content.trim() || content.trim().startsWith("#")) return;
      if (leading > indentStack[indentStack.length - 1]) {
        indentStack.push(leading);
        tokens.push({ lexeme: "    ", type: "Indent", ebnf: "INDENT" });
      } else {
        while (leading < indentStack[indentStack.length - 1]) {
          indentStack.pop();
          tokens.push({ lexeme: "", type: "Dedent", ebnf: "DEDENT" });
        }
      }
      let i = 0;
      while (i < content.length) {
        const ch = content[i];
        if (/\s/.test(ch)) { i++; continue; }
        if (ch === "#") {
          tokens.push({ lexeme: content.slice(i), type: "Comment", ebnf: "COMMENT" });
          break;
        }
        if (ch === "'" || ch === '"') {
          const quote = ch;
          let value = ch; i++;
          while (i < content.length) {
            value += content[i];
            if (content[i] === quote && content[i - 1] !== "\\") { i++; break; }
            i++;
          }
          tokens.push({ lexeme: value, type: "StringLiteral", ebnf: "STRING" });
          continue;
        }
        const number = content.slice(i).match(/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/);
        if (number) {
          tokens.push({ lexeme: number[0], type: "NumberLiteral", ebnf: "NUMBER" });
          i += number[0].length; continue;
        }
        const identifier = content.slice(i).match(/^[A-Za-z_][A-Za-z0-9_]*/);
        if (identifier) {
          const value = identifier[0];
          tokens.push({ lexeme: value, type: KEYWORDS.has(value) ? "Keyword" : "Identifier", ebnf: KEYWORDS.has(value) ? "KEYWORD" : "NAME" });
          i += value.length; continue;
        }
        const operator = OPERATORS.find((candidate) => content.startsWith(candidate, i));
        if (operator) {
          tokens.push({ lexeme: operator, type: "Operator", ebnf: "OPERATOR" });
          i += operator.length; continue;
        }
        if (DELIMITERS.has(ch)) {
          tokens.push({ lexeme: ch, type: "Delimiter", ebnf: "DELIMITER" });
          i++; continue;
        }
        tokens.push({ lexeme: ch, type: "Unknown", ebnf: "INVALID" });
        i++;
      }
      tokens.push({ lexeme: "\\n", type: "Newline", ebnf: "NEWLINE" });
    });
    while (indentStack.length > 1) {
      indentStack.pop();
      tokens.push({ lexeme: "", type: "Dedent", ebnf: "DEDENT" });
    }
    return tokens;
  }

  function getBadgeClass(type) {
    if (type === "Keyword") return "badge-keyword";
    if (type === "Identifier") return "badge-identifier";
    if (type === "NumberLiteral" || type === "StringLiteral") return "badge-literal";
    if (type === "Operator") return "badge-operator";
    if (type === "Comment") return "badge-comment";
    return "badge-delimiter";
  }

  function renderTokens(tokens) {
    tokenTableBody.innerHTML = "";
    tokenCountBadge.textContent = `${tokens.length} Tokens`;

    tokens.forEach((t, idx) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="color:#71717a">${idx + 1}</td>
        <td><strong>${escapeHtml(t.lexeme)}</strong></td>
        <td><span class="token-badge ${getBadgeClass(t.type)}">${escapeHtml(t.type)}</span></td>
        <td style="color:#2dd4bf">${escapeHtml(t.ebnf)}</td>
      `;
      tokenTableBody.appendChild(row);
    });
  }

  function runLexer() {
    const code = codeInput.value;
    ebnfOutput.textContent = "";
    grammarStatus.textContent = code.trim() ? "Validating input against the grammar..." : "Waiting for source input.";
    grammarStatus.className = "grammar-status";
    parseTreeTitle.textContent = "Concrete Parse Tree (CST)";
    astTitle.textContent = "Abstract Syntax Tree (AST)";
    const tokens = tokenize(code);
    renderTokens(tokens);
    renderTrees(code, tokens);
  }

  function jsonTree(value, key = "root", depth = 0) {
    const node = document.createElement("li");
    node.className = "json-node";
    const isBranch = value !== null && typeof value === "object";
    const label = document.createElement(isBranch ? "details" : "span");
    if (isBranch) {
      label.open = depth < 2;
      const summary = document.createElement("summary");
      summary.className = "json-branch-label";
      summary.innerHTML = `<span class="json-key">${escapeHtml(key)}</span><span class="json-kind">${Array.isArray(value) ? "array" : "object"}</span>`;
      label.appendChild(summary);
      const children = document.createElement("ul");
      Object.entries(value).forEach(([childKey, childValue]) => {
        children.appendChild(jsonTree(childValue, childKey, depth + 1));
      });
      label.appendChild(children);
    } else {
      const type = value === null ? "null" : typeof value;
      label.innerHTML = `<span class="json-key">${escapeHtml(key)}</span><span class="json-value">${escapeHtml(String(value))}</span><span class="json-type">${type}</span>`;
      label.className = `json-leaf json-${type}`;
    }
    node.appendChild(label);
    return node;
  }

  function parseCLikeSource(code, tokens) {
    const parserTokens = tokens
      .filter((token) => !["Newline", "Indent", "Dedent", "Comment"].includes(token.type))
      .map((token) => ({ value: token.lexeme, kind: token.type }));
    parserTokens.push({ value: "", kind: "EOF" });
    let index = 0;
    const current = () => parserTokens[index];
    const leaf = (token) => ({ terminal: token.value, kind: token.kind });
    const fail = (message) => { throw new Error(`${message} near ${current().value || "end of input"}`); };
    const match = (...values) => values.includes(current().value) ? parserTokens[index++] : null;
    const expect = (value) => {
      const token = match(value);
      if (!token) fail(`Expected "${value}"`);
      return token;
    };
    const expectKind = (kind) => {
      if (current().kind !== kind) fail(`Expected ${kind}`);
      return parserTokens[index++];
    };
    const binary = (operand, operators, rule) => {
      const children = [operand()];
      while (operators.includes(current().value)) children.push(leaf(parserTokens[index++]), operand());
      return { rule, children };
    };
    const expression = () => binary(comparison, ["==", "!="], "equality");
    const comparison = () => binary(additive, ["<", "<=", ">", ">="], "relational");
    const additive = () => binary(term, ["+", "-"], "additive");
    const term = () => binary(factor, ["*", "/"], "term");
    const factor = () => {
      const unary = match("+", "-");
      if (unary) return { rule: "Unary", children: [leaf(unary), factor()] };
      const opening = match("(");
      if (opening) return { rule: "Grouping", children: [leaf(opening), expression(), leaf(expect(")"))] };
      if (current().kind === "NumberLiteral") return { rule: "number", children: [leaf(parserTokens[index++])] };
      if (current().value === "true" || current().value === "false") return { rule: "BooleanLiteral", children: [leaf(parserTokens[index++])] };
      if (current().kind === "Identifier") return { rule: "Identifier", children: [leaf(parserTokens[index++])] };
      fail("Expected an expression");
    };
    const block = () => {
      const children = [leaf(expect("{"))];
      while (current().value !== "}" && current().kind !== "EOF") children.push(statement());
      children.push(leaf(expect("}")));
      return { rule: "Block", children };
    };
    const declaration = () => {
      const type = leaf(parserTokens[index++]);
      const name = leaf(expectKind("Identifier"));
      const children = [type, name];
      if (match("=")) children.push(leaf(parserTokens[index - 1]), expression());
      children.push(leaf(expect(";")));
      return { rule: "declaration", children: [{ rule: "var_decl", children }] };
    };
    const statement = () => {
      if (["int", "float", "bool", "void"].includes(current().value)) return declaration();
      if (current().value === "if" || current().value === "while") {
        const keyword = parserTokens[index++];
        const children = [leaf(keyword), leaf(expect("(")), expression(), leaf(expect(")")), block()];
        if (keyword.value === "if" && match("else")) children.push(leaf(parserTokens[index - 1]), block());
        return { rule: keyword.value === "if" ? "IfStmt" : "WhileStmt", children };
      }
      if (current().kind === "Identifier") {
        const children = [leaf(expectKind("Identifier")), leaf(expect("=")), expression(), leaf(expect(";"))];
        return { rule: "Assignment", children };
      }
      fail("Expected a C-like declaration, assignment, if statement, or while statement");
    };
    const parseTree = { rule: "Program", children: [] };
    while (current().kind !== "EOF") parseTree.children.push(statement());
    const astExpression = (node) => {
      if (["equality", "relational", "additive", "term"].includes(node.rule)) {
        let result = astExpression(node.children[0]);
        for (let i = 1; i < node.children.length; i += 2) result = { type: "BinaryExpression", operator: node.children[i].terminal, left: result, right: astExpression(node.children[i + 1]) };
        return result;
      }
      if (node.rule === "Unary") return { type: "UnaryExpression", operator: node.children[0].terminal, operand: astExpression(node.children[1]) };
      if (node.rule === "Grouping") return astExpression(node.children[1]);
      if (node.rule === "number") return { type: "Literal", value: Number(node.children[0].terminal) };
      if (node.rule === "BooleanLiteral") return { type: "Literal", value: node.children[0].terminal === "true" };
      return { type: "Identifier", name: node.children[0].terminal };
    };
    const astStatement = (node) => {
      const children = node.children;
      if (node.rule === "declaration") {
        const declarationChildren = children[0].children;
        return { type: "VariableDeclaration", dataType: declarationChildren[0].terminal, name: declarationChildren[1].terminal, initializer: declarationChildren.length === 5 ? astExpression(declarationChildren[3]) : null };
      }
      if (node.rule === "Assignment") return { type: "Assignment", name: children[0].terminal, value: astExpression(children[2]) };
      const body = children[4].children.slice(1, -1).map(astStatement);
      if (node.rule === "WhileStmt") return { type: "WhileStatement", condition: astExpression(children[2]), body };
      return { type: "IfStatement", condition: astExpression(children[2]), thenBranch: body, elseBranch: children[6] ? children[6].children.slice(1, -1).map(astStatement) : null };
    };
    return { parseTree, ast: { type: "Program", statements: parseTree.children.map(astStatement) } };
  }

  function parseSource(code, tokens) {
    return parseCLikeSource(code, tokens);
    /* Legacy parser retained below for reference. */
    const lines = code.replace(/\r\n?/g, "\n").split("\n");
    const leaf = (value, kind = "Identifier") => ({ terminal: value, kind });
    const expressionAst = (source) => {
      const text = source.trim();
      if (text.startsWith("(") && text.endsWith(")") && matchingOuterParens(text)) {
        return expressionAst(text.slice(1, -1));
      }
      if (/^[-+]?\d+(?:\.\d+)?$/.test(text)) return { type: "Literal", value: Number(text) };
      if (/^(['"]).*\1$/.test(text)) return { type: "Literal", value: text.slice(1, -1) };
      if (/^(True|False|None)$/.test(text)) return { type: "Literal", value: text === "True" ? true : text === "False" ? false : null };
      const call = text.match(/^([A-Za-z_]\w*)\((.*)\)$/);
      if (call) return { type: "CallExpression", callee: call[1], arguments: call[2] ? call[2].split(",").map(expressionAst) : [] };
      const binary = splitBinary(text);
      if (binary) return { type: "BinaryExpression", operator: binary.operator, left: expressionAst(binary.left), right: expressionAst(binary.right) };
      if (/^[A-Za-z_]\w*$/.test(text)) return { type: "Identifier", name: text };
      throw new Error(`Invalid expression near ${text || "end of input"}`);
    };
    const expressionCst = (source) => {
      const text = source.trim();
      if (text.startsWith("(") && text.endsWith(")") && matchingOuterParens(text)) {
        return { rule: "grouping", children: [leaf("(", "Delimiter"), expressionCst(text.slice(1, -1)), leaf(")", "Delimiter")] };
      }
      const binary = splitBinary(text);
      if (binary) return { rule: "expression", children: [expressionCst(binary.left), leaf(binary.operator, "Operator"), expressionCst(binary.right)] };
      if (/^(['"]).*\1$/.test(text)) return { rule: "string", children: [leaf(text, "StringLiteral")] };
      if (/^\d+(?:\.\d+)?$/.test(text)) return { rule: "number", children: [leaf(text, "NumberLiteral")] };
      if (/^(True|False|None)$/.test(text)) return { rule: "constant", children: [leaf(text, "Keyword")] };
      const call = text.match(/^([A-Za-z_]\w*)\((.*)\)$/);
      if (call) return { rule: "call", children: [leaf(call[1]), leaf("(" , "Delimiter"), ...(call[2] ? [expressionCst(call[2])] : []), leaf(")", "Delimiter")] };
      if (/^[A-Za-z_]\w*$/.test(text)) return { rule: "identifier", children: [leaf(text)] };
      throw new Error(`Invalid expression near ${text || "end of input"}`);
    };
    const matchingOuterParens = (text) => {
      let depth = 0;
      for (let index = 0; index < text.length; index += 1) {
        if (text[index] === "(") depth += 1;
        if (text[index] === ")") depth -= 1;
        if (depth === 0 && index < text.length - 1) return false;
      }
      return depth === 0;
    };
    const splitBinary = (text) => {
      const precedenceLevels = [
        ["==", "!=", "<=", ">=", "<", ">"],
        ["+", "-"],
        ["*", "/", "%"],
      ];
      for (const operators of precedenceLevels) {
        let depth = 0;
        for (let index = text.length - 1; index >= 0; index -= 1) {
          if (text[index] === ")") depth += 1;
          if (text[index] === "(") depth -= 1;
          if (depth !== 0) continue;
          for (const operator of operators) {
            const start = index - operator.length + 1;
            if (start > 0 && index < text.length - 1 && text.slice(start, index + 1) === operator) {
              return { left: text.slice(0, start), operator, right: text.slice(index + 1) };
            }
          }
        }
      }
      return null;
    };
    const cst = { rule: "Program", children: [] };
    const ast = { type: "Module", body: [] };
    lines.forEach((line, lineIndex) => {
      const text = line.trim();
      if (!text || text.startsWith("#")) return;
      const lineNumber = lineIndex + 1;
      const tokensForLine = tokenize(text).filter((token) => !["Newline", "Indent", "Dedent"].includes(token.type));
      const terminals = tokensForLine.map((token) => leaf(token.lexeme, token.type));
      const assignment = text.match(/^([A-Za-z_]\w*)\s*([+\-*/%]?=)\s*(.+)$/);
      if (assignment) {
        const [, name, operator, value] = assignment;
        const node = { rule: "Assignment", children: [leaf(name), leaf(operator, "Operator"), expressionCst(value)] };
        cst.children.push(node);
        ast.body.push({ type: "Assignment", target: { type: "Identifier", name }, operator, value: expressionAst(value) });
        return;
      }
      const control = text.match(/^(if|while|for)\s+(.+):$/);
      if (control) {
        const rule = control[1] === "if" ? "IfStatement" : control[1] === "while" ? "WhileStatement" : "ForStatement";
        cst.children.push({ rule, children: terminals });
        ast.body.push({ type: rule, condition: expressionAst(control[2]) });
        return;
      }
      if (/^(return|pass|break)\b/.test(text)) {
        const keyword = text.match(/^(\w+)/)[1];
        cst.children.push({ rule: `${keyword}Statement`, children: terminals });
        ast.body.push({ type: `${keyword[0].toUpperCase()}${keyword.slice(1)}Statement` });
        return;
      }
      if (/^[A-Za-z_]\w*\s*\(.*\)$/.test(text)) {
        cst.children.push({ rule: "ExpressionStatement", children: terminals });
        ast.body.push({ type: "ExpressionStatement", expression: expressionAst(text) });
        return;
      }
      throw new Error(`Unsupported C-like statement on line ${lineNumber} near ${text}`);
    });
    return { parseTree: cst, ast };
  }

  function parsePythonSource(code, tokens) {
    const lines = code.replace(/\r\n?/g, "\n").split("\n");
    const meaningful = lines
      .map((text, index) => ({ text, index: index + 1, indent: text.match(/^[ \t]*/)[0].replace(/\t/g, "    ").length }))
      .filter((line) => line.text.trim() && !line.text.trim().startsWith("#"));
    const expressionAst = (source) => {
      const value = source.trim();
      if (/^(True|False|None)$/.test(value)) return { type: "Constant", value: value === "True" ? true : value === "False" ? false : null };
      if (/^(['"]).*\1$/.test(value)) return { type: "Constant", value: value.slice(1, -1) };
      if (/^-?\d+(?:\.\d+)?$/.test(value)) return { type: "Constant", value: Number(value) };
      const call = value.match(/^([A-Za-z_]\w*)\((.*)\)$/);
      if (call) return { type: "Call", function: { type: "Name", id: call[1] }, arguments: call[2] ? call[2].split(",").map(expressionAst) : [] };
      const binary = value.match(/^(.+?)\s(==|!=|<=|>=|<|>|\+|-|\*|\/|%|and|or)\s(.+)$/);
      if (binary) return { type: "BinOp", operator: binary[2], left: expressionAst(binary[1]), right: expressionAst(binary[3]) };
      return { type: "Name", id: value };
    };
    const astForLine = (source) => {
      const text = source.trim();
      let match = text.match(/^def\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*:/);
      if (match) return { type: "FunctionDef", name: match[1], arguments: match[2] ? match[2].split(",").map((name) => name.trim()).filter(Boolean) : [] };
      match = text.match(/^(if|elif|while)\s+(.+):$/);
      if (match) return { type: match[1] === "if" ? "If" : match[1] === "elif" ? "Elif" : "While", test: expressionAst(match[2]), body: [] };
      match = text.match(/^for\s+([A-Za-z_]\w*)\s+in\s+(.+):$/);
      if (match) return { type: "For", target: { type: "Name", id: match[1] }, iterable: expressionAst(match[2]), body: [] };
      match = text.match(/^return(?:\s+(.+))?$/);
      if (match) return { type: "Return", value: match[1] ? expressionAst(match[1]) : null };
      match = text.match(/^([A-Za-z_]\w*)\s*([+\-*\/%]?=)\s*(.+)$/);
      if (match) return { type: "Assign", target: { type: "Name", id: match[1] }, operator: match[2], value: expressionAst(match[3]) };
      return { type: "Expr", value: expressionAst(text) };
    };
    const cst = {
      rule: "PythonModule",
      children: meaningful.map((line) => ({
        rule: "PythonStatement",
        line: line.index,
        indent: line.indent,
        children: tokenize(line.text).filter((token) => !["Indent", "Dedent", "Newline"].includes(token.type)).map((token) => ({ terminal: token.lexeme, kind: token.type })),
      })),
    };
    const ast = { type: "Module", body: meaningful.map((line) => astForLine(line.text)) };
    const invalid = tokens.find((token) => token.type === "Unknown");
    if (invalid) throw new Error(`Unsupported C-like character "${invalid.lexeme}"`);
    return { parseTree: cst, ast };
  }

  function renderTrees(code, tokens) {
    parseTreeOutput.classList.remove("tree-output", "tree-error");
    astOutput.classList.remove("tree-output", "tree-error");
    if (!code.trim()) {
      grammarStatus.textContent = "Waiting for source input.";
      grammarStatus.className = "grammar-status";
      parseTreeOutput.innerHTML = "<p>Enter code to generate the concrete parse tree.</p>";
      astOutput.innerHTML = "<p>Enter code to generate the abstract syntax tree.</p>";
      return;
    }
    try {
      const result = parseSource(code, tokens);
      ebnfOutput.textContent = buildInputGrammar(result.parseTree);
      grammarStatus.textContent = "Valid: input matches the displayed EBNF grammar.";
      grammarStatus.className = "grammar-status grammar-valid";
      parseTreeOutput.classList.add("tree-output");
      astOutput.classList.add("tree-output");
      renderMermaidTree(parseTreeOutput, result.parseTree, "cst");
      renderMermaidTree(astOutput, result.ast, "ast");
    } catch (error) {
      ebnfOutput.textContent = "";
      grammarStatus.textContent = `Invalid: ${error.message}`;
      grammarStatus.className = "grammar-status grammar-invalid";
      const message = escapeHtml(error.message);
      parseTreeOutput.classList.add("tree-error");
      astOutput.classList.add("tree-error");
      parseTreeOutput.innerHTML = `<p><strong>CST parse error</strong></p><p>${message}</p>`;
      astOutput.innerHTML = `<p><strong>AST unavailable</strong></p><p>Fix the CST syntax error first:</p><p>${message}</p>`;
    }
  }

  function buildInputGrammar(parseTree) {
    const productions = [];
    const seen = new Set();
    const identifiers = [];
    const numbers = [];
    const booleans = [];
    const types = [];
    const add = (rule, production) => {
      if (!seen.has(rule)) {
        seen.add(rule);
        productions.push(`${rule} = ${production} ;`);
      }
    };
    const collect = (node) => {
      if (!node || typeof node !== "object") return;
      if (node.rule === "Program") add("program", "statement");
      if (node.rule === "declaration") add("statement", "var_decl");
      if (node.rule === "var_decl") {
        add("var_decl", node.children.length === 5
          ? 'type, identifier, [ "=", expression ], ";"'
          : 'type, identifier, ";"');
        const type = node.children[0]?.terminal;
        if (type && !types.includes(type)) types.push(type);
      }
      if (node.rule === "Assignment") add("statement", "assignment");
      if (node.rule === "Assignment") add("assignment", 'identifier, "=", expression, ";"');
      if (node.rule === "ExpressionStatement") add("statement", "expression_stmt");
      if (node.rule === "expression") add("expression", 'term, { ( "+" | "-" | "*" | "/" | "%" | "==" | "!=" | "<" | ">" | "<=" | ">=" ), term }');
      if (node.rule === "string") add("primary", "string");
      if (node.rule === "constant") add("primary", "constant");
      if (node.rule === "call") add("primary", "call");
      if (node.rule === "grouping") add("primary", '"(", expression, ")"');
      if (node.rule === "IfStmt") {
        add("statement", "if_stmt");
        add("if_stmt", '"if", "(", expression, ")", block, [ "else", block ]');
      }
      if (node.rule === "WhileStmt") {
        add("statement", "while_stmt");
        add("while_stmt", '"while", "(", expression, ")", block');
      }
      if (node.rule === "Block") add("block", '"{", { statement }, "}"');
      if (["equality", "relational", "additive", "term"].includes(node.rule)) {
        const expressions = {
          equality: 'relational, { ( "==" | "!=" ), relational }',
          relational: 'additive, { ( "<" | ">" | "<=" | ">=" ), additive }',
          additive: 'term, { ( "+" | "-" ), term }',
          term: 'factor, { ( "*" | "/" ), factor }',
        };
        add("expression", "equality");
        add(node.rule, expressions[node.rule]);
      }
      if (node.rule === "Identifier") {
        add("factor", "identifier");
        const value = node.children[0].terminal;
        if (!identifiers.includes(value)) identifiers.push(value);
      }
      if (node.rule === "number") {
        add("factor", "number");
        const value = node.children[0].terminal;
        if (!numbers.includes(value)) numbers.push(value);
      }
      if (node.rule === "BooleanLiteral") {
        add("factor", "boolean");
        const value = node.children[0].terminal;
        if (!booleans.includes(value)) booleans.push(value);
      }
      if (Array.isArray(node.children)) {
        node.children.forEach((child) => {
          if (child?.terminal !== undefined) {
            if (child.kind === "Identifier" && !identifiers.includes(child.terminal)) {
              identifiers.push(child.terminal);
            }
            if (child.kind === "NumberLiteral" && !numbers.includes(child.terminal)) {
              numbers.push(child.terminal);
            }
            if (child.kind === "StringLiteral") add("string", `"${child.terminal.slice(1, -1)}"`);
          }
          collect(child);
        });
      }
    };
    collect(parseTree);
    if (identifiers.length) add("identifier", identifiers.map((value) => `"${value}"`).join(" | "));
    if (numbers.length) add("number", numbers.map((value) => `"${value}"`).join(" | "));
    if (booleans.length) add("boolean", booleans.map((value) => `"${value}"`).join(" | "));
    if (types.length) add("type", types.map((value) => `"${value}"`).join(" | "));
    const syntaxProductions = productions.filter((production) => !/^(identifier|number|boolean|type|string) =/.test(production));
    const terminalProductions = productions.filter((production) => /^(identifier|number|boolean|type|string) =/.test(production));
    return [
      "(* Generated from the current input *)",
      ...syntaxProductions,
      "",
      "(* Input-specific terminals *)",
      ...terminalProductions,
    ].filter((line, index, lines) => line || lines[index - 1] !== "").join("\n");
  }

  function renderMermaidTree(container, value, mode) {
    container.classList.remove("mermaid-cst", "mermaid-ast");
    container.classList.add(`mermaid-${mode}`);
    if (!window.mermaid) {
      container.classList.add("tree-error");
      container.innerHTML = "<p>Tree renderer unavailable. Check your connection and reload the page.</p>";
      return;
    }

    const diagram = buildMermaidTree(value, mode);
    container.innerHTML = `<div class="mermaid">${diagram}</div>`;
    const diagramId = `${mode}Tree${Date.now()}${Math.floor(Math.random() * 1000)}`;
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
    window.mermaid.render(diagramId, diagram)
      .then(({ svg, bindFunctions }) => {
        container.innerHTML = svg;
        container.querySelector("svg")?.setAttribute("aria-label", `${mode === "cst" ? "Concrete parse" : "Abstract syntax"} tree`);
        if (bindFunctions) bindFunctions(container);
      })
      .catch((error) => {
        container.classList.add("tree-error");
        container.innerHTML = `<p>Unable to draw tree: ${escapeHtml(error.message)}</p>`;
      });
  }

  function buildMermaidTree(value, mode) {
    const lines = [
      "flowchart TD",
      "classDef root fill:transparent,stroke:#5eead4,color:#ecfeff,stroke-width:3px",
      "classDef node fill:transparent,stroke:#22d3ee,color:#ecfeff,stroke-width:2px",
      "classDef ast fill:transparent,stroke:#d8b4fe,color:#faf5ff,stroke-width:2px",
      "classDef terminal fill:transparent,stroke:#facc15,color:#fef9c3,stroke-width:2px",
      "classDef field fill:transparent,stroke:#a1a1aa,color:#f4f4f5,stroke-width:2px",
    ];
    let index = 0;
    const addNode = (nodeValue, label, parentId = null, isRoot = false) => {
      const id = `treeNode${index++}`;
      if (nodeValue && typeof nodeValue === "object" && nodeValue.terminal !== undefined) {
        label = `"${nodeValue.terminal}"\n${nodeValue.kind}`;
      } else if (nodeValue === null || typeof nodeValue !== "object") {
        label = `${label}: ${nodeValue}`;
      }
      const nodeClass = isRoot ? "root" : mode === "ast" ? "ast" : nodeValue && nodeValue.terminal !== undefined ? "terminal" : "node";
      lines.push(`${id}["${mermaidLabel(label)}"]:::${nodeClass}`);
      if (parentId) lines.push(`${parentId} --> ${id}`);

      if (nodeValue && typeof nodeValue === "object") {
        if (mode === "cst" && nodeValue.terminal !== undefined) return id;
        Object.entries(nodeValue).forEach(([key, child]) => {
          if (mode === "cst" && key === "rule") return;
          if (mode === "ast" && key === "type") return;
          if (Array.isArray(child)) {
            child.forEach((entry, childIndex) => addNode(entry, `${key}[${childIndex}]`, id));
          } else {
            addNode(child, key, id);
          }
        });
      }
      return id;
    };

    const rootLabel = mode === "cst" ? value.rule || "Program" : value.type || "Program";
    addNode(value, rootLabel, null, true);
    return lines.join("\n");
  }

  function mermaidLabel(value) {
    return String(value)
      .replace(/\\/g, "\\\\")
      .replace(/"/g, "#quot;")
      .replace(/</g, "#lt;")
      .replace(/>/g, "#gt;")
      .replace(/\n/g, "<br/>");
  }

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  }

  runBtn.addEventListener("click", runLexer);

  codeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        runLexer();
      }
    }
  });

  let analysisTimer;
  codeInput.addEventListener("input", () => {
    clearTimeout(analysisTimer);
    analysisTimer = setTimeout(runLexer, 300);
  });

  const grammarExamples = [
  "int x = 10;",
  "total = x + 5;",
  "if (total > 10) { total = total + 1; }",
  ];

  presetBtns.forEach((btn, index) => {
    if (grammarExamples[index]) {
      btn.setAttribute("data-code", grammarExamples[index]);
    }
    btn.addEventListener("click", () => {
      codeInput.value = btn.getAttribute("data-code");
      runLexer();
    });
  });

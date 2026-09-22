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

  // --- 3. LEXER / TOKENIZER CORE (25% MILESTONE) ---
  const codeInput = document.getElementById("codeInput");
  const runBtn = document.getElementById("runBtn");
  const tokenTableBody = document.getElementById("tokenTableBody");
  const tokenCountBadge = document.getElementById("tokenCountBadge");
  const presetBtns = document.querySelectorAll(".preset-btn");

  const KEYWORDS = ["let", "const", "var", "if", "else", "while", "true", "false"];
  const REL_OPS = ["==", "!=", "<=", ">=", "<", ">"];
  const ARITH_OPS = ["+", "-", "*", "/", "="];
  const DELIMITERS = [";", "(", ")", "{", "}", ","];

  function tokenize(code) {
    const tokens = [];
    let i = 0;

    while (i < code.length) {
      const ch = code[i];

      // Skip whitespace
      if (/\s/.test(ch)) {
        i++;
        continue;
      }

      // Delimiters
      if (DELIMITERS.includes(ch)) {
        tokens.push({ lexeme: ch, type: "Delimiter", ebnf: 'Delimiter = "' + ch + '"' });
        i++;
        continue;
      }

      // Multi-char relational operators (==, !=, <=, >=)
      const twoChar = code.slice(i, i + 2);
      if (REL_OPS.includes(twoChar)) {
        tokens.push({ lexeme: twoChar, type: "RelationalOp", ebnf: "RelOp" });
        i += 2;
        continue;
      }

      // Single-char relational or arithmetic operators
      if (REL_OPS.includes(ch)) {
        tokens.push({ lexeme: ch, type: "RelationalOp", ebnf: "RelOp" });
        i++;
        continue;
      }
      if (ARITH_OPS.includes(ch)) {
        tokens.push({ lexeme: ch, type: "ArithmeticOp", ebnf: ch === "=" ? 'AssignOp = "="' : "ArithOp" });
        i++;
        continue;
      }

      // Numbers / IntLiteral
      if (/[0-9]/.test(ch)) {
        let num = "";
        while (i < code.length && /[0-9]/.test(code[i])) {
          num += code[i];
          i++;
        }
        tokens.push({ lexeme: num, type: "IntLiteral", ebnf: "IntLiteral = Digit, { Digit }" });
        continue;
      }

      // Identifiers & Keywords
      if (/[a-zA-Z_]/.test(ch)) {
        let ident = "";
        while (i < code.length && /[a-zA-Z0-9_]/.test(code[i])) {
          ident += code[i];
          i++;
        }
        if (KEYWORDS.includes(ident)) {
          tokens.push({ lexeme: ident, type: "Keyword", ebnf: ident === "let" || ident === "const" || ident === "var" ? "VarKeyword" : "ControlKeyword" });
        } else {
          tokens.push({ lexeme: ident, type: "Identifier", ebnf: "Identifier = Letter, { Letter | Digit }" });
        }
        continue;
      }

      // Unrecognized character fallback
      tokens.push({ lexeme: ch, type: "Unknown", ebnf: "UndefinedTerminal" });
      i++;
    }

    return tokens;
  }

  function getBadgeClass(type) {
    if (type === "Keyword") return "badge-keyword";
    if (type === "Identifier") return "badge-identifier";
    if (type === "IntLiteral") return "badge-literal";
    if (type.includes("Op")) return "badge-operator";
    return "badge-delimiter";
  }

  function renderTokens(tokens) {
    tokenTableBody.innerHTML = "";
    tokenCountBadge.textContent = `${tokens.length} Tokens`;

    tokens.forEach((t, idx) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="color:#71717a">${idx + 1}</td>
        <td><strong>${t.lexeme}</strong></td>
        <td><span class="token-badge ${getBadgeClass(t.type)}">${t.type}</span></td>
        <td style="color:#2dd4bf">${t.ebnf}</td>
      `;
      tokenTableBody.appendChild(row);
    });
  }

  function runLexer() {
    const code = codeInput.value;
    const tokens = tokenize(code);
    renderTokens(tokens);
  }

  runBtn.addEventListener("click", runLexer);

  codeInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      runLexer();
    }
  });

  presetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      codeInput.value = btn.getAttribute("data-code");
      runLexer();
    });
  });

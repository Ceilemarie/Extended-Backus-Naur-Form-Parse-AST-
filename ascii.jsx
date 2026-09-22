"use client";

import React, { useEffect, useRef, useState } from "react";

export default function SandHero({ imageSrc = "/liminal-stack.png" }) {
  const canvasRef = useRef(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const particlesRef = useRef([]);
  const mouseRef = useRef({ x: -1000, y: -1000, isDown: false, radius: 40 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const img = new Image();
    img.src = imageSrc;
    img.crossOrigin = "anonymous";

    class Particle {
      constructor(x, y, color) {
        this.originX = x;
        this.originY = y;
        this.x = x;
        this.y = y;
        this.vx = (Math.random() - 0.5) * 1.5;
        this.vy = (Math.random() - 0.5) * 1.5;
        this.color = color;
        this.isFalling = false;
      }

      update(width, height) {
        const mouse = mouseRef.current;
        const dx = mouse.x - this.x;
        const dy = mouse.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Trigger sand collapse on hover or click
        const triggerRadius = mouse.isDown ? mouse.radius * 1.8 : mouse.radius;
        if (dist < triggerRadius) {
          this.isFalling = true;
          const force = (triggerRadius - dist) / triggerRadius;
          const angle = Math.atan2(dy, dx);
          this.vx -= Math.cos(angle) * force * 6;
          this.vy -= Math.sin(angle) * force * 6;
        }

        if (this.isFalling) {
          this.vy += 0.22; // Sand gravity
          this.vx *= 0.94; // Air resistance
          this.vy *= 0.94;

          this.x += this.vx;
          this.y += this.vy;

          // Floor collision
          if (this.y >= height - 2) {
            this.y = height - 2;
            this.vy = 0;
            this.vx *= 0.6; // Sand ground friction
          }

          // Wall boundaries
          if (this.x < 0) this.x = 0;
          if (this.x > width) this.x = width;
        }
      }

      draw(context) {
        context.fillStyle = this.color;
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

    img.onload = () => {
      // Dimensions ng canvas canvas viewport
      const targetW = 380;
      const targetH = 320;
      canvas.width = targetW;
      canvas.height = targetH;

      const offscreen = document.createElement("canvas");
      const offCtx = offscreen.getContext("2d");
      offscreen.width = targetW;
      offscreen.height = targetH;

      // Draw and extract pixels
      offCtx.drawImage(img, 0, 0, targetW, targetH);
      const imgData = offCtx.getImageData(0, 0, targetW, targetH).data;

      const particles = [];
      const step = 2; // Density control (2 = high res, 3 = faster performance)

      for (let y = 0; y < targetH; y += step) {
        for (let x = 0; x < targetW; x += step) {
          const idx = (y * targetW + x) * 4;
          const r = imgData[idx];
          const alpha = imgData[idx + 3];

          // Target ang dark/black dithered pixels ng image
          if (alpha > 120 && r < 120) {
            // Gumamit ng luminescent cyberpunk terminal tone
            const color = "#5eead4"; // Tailwind teal-300 / mint glow
            particles.push(new Particle(x, y, color));
          }
        }
      }

      particlesRef.current = particles;
      setIsLoaded(true);

      let animId;
      const render = () => {
        // Dark background clearing with soft persistence trail
        ctx.fillStyle = "rgba(9, 9, 11, 0.4)"; // matches zinc-950
        ctx.fillRect(0, 0, targetW, targetH);

        for (let i = 0; i < particles.length; i++) {
          particles[i].update(targetW, targetH);
          particles[i].draw(ctx);
        }

        animId = requestAnimationFrame(render);
      };

      render();

      return () => cancelAnimationFrame(animId);
    };

    // Mouse Interactions
    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.x = e.clientX - rect.left;
      mouseRef.current.y = e.clientY - rect.top;
    };

    const handleMouseDown = () => {
      mouseRef.current.isDown = true;
    };

    const handleMouseUp = () => {
      mouseRef.current.isDown = false;
    };

    const handleMouseLeave = () => {
      mouseRef.current.x = -1000;
      mouseRef.current.y = -1000;
      mouseRef.current.isDown = false;
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [imageSrc]);

  const handleReset = () => {
    particlesRef.current.forEach((p) => p.reset());
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-4 rounded-xl border border-zinc-800 bg-zinc-950/80 backdrop-blur-sm shadow-2xl">
      <div className="absolute top-3 left-4 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
        <span className="text-[11px] font-mono tracking-widest text-zinc-400 uppercase">
          Dither Subsystem // Sand Physics
        </span>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border border-zinc-800/60 bg-zinc-950">
        <canvas
          ref={canvasRef}
          className="cursor-crosshair active:cursor-grabbing select-none"
        />
      </div>

      <div className="mt-3 flex items-center justify-between w-full px-2 text-[12px] font-mono text-zinc-500">
        <span>Click or Drag over image to scatter</span>
        <button
          onClick={handleReset}
          className="px-2.5 py-1 text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/60 rounded transition-colors text-xs"
        >
          Restore
        </button>
      </div>
    </div>
  );
}
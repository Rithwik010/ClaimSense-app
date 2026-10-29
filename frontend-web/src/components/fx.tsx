// Small, restrained motion pieces (DESIGN.md, D-UI-5), written here on Motion and Tailwind rather
// than installed: a blur-fade entrance, a spotlight card, a count-up for counts, the logo, and the
// login page's pipeline beam (ideas from Magic UI's Blur Fade, Magic Card, Number Ticker and
// Animated Beam). Every one respects prefers-reduced-motion through MotionConfig in main.tsx.
// Money and decisions are never animated: NumberTicker is for counts only.

import { animate, motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";

/** Fades and un-blurs its children once, rising 6 px. */
export function BlurFade({
  children,
  delay = 0,
  className,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li";
}) {
  const reduce = useReducedMotion();
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y: 6, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </Tag>
  );
}

/** A card whose border and fill catch a soft light that follows the pointer. */
export function Spotlight({
  children,
  className = "",
  glass = true,
  ...rest
}: { children: ReactNode; className?: string; glass?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box || !ref.current) return;
    ref.current.style.setProperty("--spot-x", `${event.clientX - box.left}px`);
    ref.current.style.setProperty("--spot-y", `${event.clientY - box.top}px`);
  };
  return (
    <div
      ref={ref}
      onPointerMove={move}
      className={`group/spot relative overflow-hidden rounded-lg ${glass ? "glass" : "surface"} ${className}`}
      style={{ "--spot-x": "50%", "--spot-y": "0px" } as CSSProperties}
      {...rest}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
        style={{
          background:
            "radial-gradient(320px circle at var(--spot-x) var(--spot-y), rgb(36 66 214 / 0.06), transparent 65%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

/** Counts up to a whole number once, on first render. The final value is what screen readers get. */
export function NumberTicker({ value, className = "" }: { value: number; className?: string }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const controls = animate(0, value, {
      duration: Math.min(1.2, 0.4 + value * 0.04),
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => setShown(Math.round(latest)),
    });
    return () => controls.stop();
  }, [value, reduce]);
  return (
    <span className={`tabular-nums ${className}`}>
      <span aria-hidden>{reduce ? value : shown}</span>
      <span className="sr-only">{value}</span>
    </span>
  );
}

/** The ClaimSense mark: a shield (trust), a pulse (health), and a dot (a person confirms); white
 * on the blue sidebar, the action blue on a white page. */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden className={className}>
      <rect width="48" height="48" rx="10" fill="#FFFFFF" />
      <rect x="0.5" y="0.5" width="47" height="47" rx="9.5" stroke="#D9DCE3" />
      <path d="M24 9 36.5 13.8v9.6c0 7.4-5 12.7-12.5 15.6C16.5 36.1 11.5 30.8 11.5 23.4v-9.6z" fill="#2442D6" />
      <path
        d="M15.8 24.2h4.3l2.7-6.8 4 12.6 2.7-5.8h3"
        stroke="#FFFFFF"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="33.6" cy="24.2" r="2.3" fill="#E8ECFF" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-heading font-bold tracking-[-0.01em] ${className}`}>ClaimSense</span>
  );
}

const STAGES = ["Intake", "Rules", "Policy", "Model", "Amounts", "Explanation", "Review", "Audit"];

/**
 * The pipeline on the login page's blue panel: eight stages in two rows joined by one path; a short band of
 * light travels along it slowly. Decorative: the stage names are also in the text beside it.
 */
export function PipelineBeam() {
  const reduce = useReducedMotion();
  const id = useId().replace(/:/g, "");
  // Two rows of four, read like the claim moves: left to right, down, then right to left.
  const W = 520;
  const col = (i: number) => 40 + (i % 4) * ((W - 80) / 3);
  const pos = STAGES.map((_, i) => (i < 4 ? { x: col(i), y: 40 } : { x: col(7 - i), y: 168 }));
  const path = `M${pos[0]!.x} 40 H${pos[3]!.x} C ${pos[3]!.x + 70} 40, ${pos[4]!.x + 70} 168, ${pos[4]!.x} 168 H${pos[7]!.x}`;
  return (
    <div className="relative mx-auto w-full max-w-[520px]" aria-hidden>
      <svg viewBox={`0 0 ${W} 220`} className="w-full overflow-visible">
        <defs>
          <linearGradient id={`beam-${id}`} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="0.4" stopColor="#FFFFFF" />
            <stop offset="0.7" stopColor="#E8ECFF" />
            <stop offset="1" stopColor="#E8ECFF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={path} stroke="rgb(255 255 255 / 0.35)" strokeWidth="1.5" fill="none" />
        <motion.path
          d={path}
          stroke={`url(#beam-${id})`}
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
          strokeDasharray="90 1400"
          initial={{ strokeDashoffset: reduce ? -400 : 90 }}
          animate={reduce ? undefined : { strokeDashoffset: -1400 }}
          transition={{ duration: 7, ease: "linear", repeat: Infinity, repeatDelay: 1 }}
        />
      </svg>
      {pos.map((p, i) => (
        <div
          key={STAGES[i]}
          className="absolute flex -translate-x-1/2 -translate-y-[22px] flex-col items-center gap-2"
          style={{ left: `${(p.x / W) * 100}%`, top: `${(p.y / 220) * 100}%` }}
        >
          <span
            className={`grid size-11 place-items-center rounded-full border text-[12px] font-semibold ${
              STAGES[i] === "Review"
                ? "border-white bg-ink-strong text-white"
                : "border-white/60 bg-white text-ink-strong"
            }`}
          >
            {i + 1}
          </span>
          <span className="text-[13px] font-semibold whitespace-nowrap text-[#e8ecff]">{STAGES[i]}</span>
        </div>
      ))}
    </div>
  );
}

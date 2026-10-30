// Small, restrained motion pieces (DESIGN.md, D-UI-5), written here on Motion and Tailwind rather
// than installed: a blur-fade entrance, a spotlight card, a count-up for counts and the logo (ideas
// from Magic UI's Blur Fade, Magic Card and Number Ticker). Every one respects
// prefers-reduced-motion through MotionConfig in main.tsx.
// Money and decisions are never animated: NumberTicker is for counts only.

import { animate, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";

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
      <path d="M24 9 36.5 13.8v9.6c0 7.4-5 12.7-12.5 15.6C16.5 36.1 11.5 30.8 11.5 23.4v-9.6z" fill="#0033ff" />
      <path
        d="M15.8 24.2h4.3l2.7-6.8 4 12.6 2.7-5.8h3"
        stroke="#FFFFFF"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="33.6" cy="24.2" r="2.3" fill="#e6ebff" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-heading font-bold tracking-[-0.01em] ${className}`}>ClaimSense</span>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";

// design.md §6 reveal-on-scroll: translateY 30px→0, opacity 0→1, 0.8s ease —
// triggered as each section actually enters the viewport (IntersectionObserver),
// not on mount. Used on the marketing page's scrolling sections; the exam
// app's own screens use the plain mount-triggered `animate-reveal` utility
// instead, since those are short, non-scrolling screens.
export function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`transition-all duration-[800ms] ease-out ${
        visible ? "translate-y-0 opacity-100" : "translate-y-[30px] opacity-0"
      } ${className}`}
    >
      {children}
    </div>
  );
}

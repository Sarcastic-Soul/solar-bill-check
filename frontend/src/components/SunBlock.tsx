import type { ReactNode } from "react";
import { m, LazyMotion, domAnimation, useReducedMotion } from "motion/react";

/** The amber poster block with the sun drawing and a giant number. */
export default function SunBlock({ tag, value, unit, children }: { tag: string; value: string; unit: string; children?: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <LazyMotion features={domAnimation} strict>
      <div className="relative h-full min-h-[420px] overflow-hidden bg-sun md:min-h-[520px]">
        <svg className="absolute inset-0 size-full" viewBox="0 0 400 520" preserveAspectRatio="xMidYMid slice" aria-hidden>
          <path d="M-20 330 A 230 230 0 0 1 420 330" fill="none" stroke="#1A1814" strokeWidth="2" strokeDasharray="2 8" />
          <m.g
            initial={reduce ? false : { y: 60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", bounce: 0, duration: 0.9, delay: 0.15 }}
          >
            <circle cx="292" cy="148" r="46" fill="#ECEDEA" stroke="#1A1814" strokeWidth="2" />
            <g stroke="#1A1814" strokeWidth="2">
              <line x1="292" y1="80" x2="292" y2="64" />
              <line x1="292" y1="216" x2="292" y2="232" />
              <line x1="224" y1="148" x2="208" y2="148" />
              <line x1="360" y1="148" x2="376" y2="148" />
              <line x1="244" y1="100" x2="233" y2="89" />
              <line x1="340" y1="196" x2="351" y2="207" />
              <line x1="340" y1="100" x2="351" y2="89" />
              <line x1="244" y1="196" x2="233" y2="207" />
            </g>
          </m.g>
        </svg>
        <span className="eyebrow absolute left-5 top-5 border-2 border-ink bg-paper px-2.5 py-1.5 md:left-7 md:top-6">{tag}</span>
        <div className="absolute inset-x-5 bottom-6 md:inset-x-7">
          <m.div
            initial={reduce ? false : { y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", bounce: 0, duration: 0.7 }}
            className="flex items-end gap-2"
          >
            <span className="display tabular text-[clamp(112px,15vw,200px)] font-bold leading-[0.8] tracking-[-0.04em]">{value}</span>
            <span className="display pb-1 text-[26px] font-semibold">{unit}</span>
          </m.div>
          {children ? <div className="mt-3 max-w-[24em] text-[16px] font-medium">{children}</div> : null}
        </div>
      </div>
    </LazyMotion>
  );
}

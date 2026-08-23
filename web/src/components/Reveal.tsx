"use client";

/**
 * A rise-on-enter wrapper.
 *
 * Deliberately CSS-only rather than an IntersectionObserver: the effect is
 * decoration, and content that is invisible until JavaScript decides otherwise
 * is a real accessibility cost for a decorative gain. Here the animation starts
 * from opacity 0 but the element is in the document and in the accessibility
 * tree from the first paint, and `prefers-reduced-motion` collapses the
 * duration to nothing via globals.css.
 */
export default function Reveal({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <div style={{ animation: `rise .7s cubic-bezier(.2,.7,.2,1) ${delay}s both` }}>
      {children}
    </div>
  );
}

// Uses the .skeleton class from index.css for the shimmer keyframe.
// The class provides: overflow:hidden, position:relative, bg-elevated fill,
// and a ::after pseudo-element that sweeps rgba(255,255,255,0.05) at 1.8s.
// This component adds glassmorphism + controlled width/height/radius on top.

interface SkeletonGlassProps {
  width?:  string;
  height?: string;
  radius?: number;
}

export function SkeletonGlass({ width = '100%', height = '20px', radius = 8 }: SkeletonGlassProps) {
  return (
    <span
      className="skeleton"
      style={{
        display: 'block',
        width,
        height,
        borderRadius: radius,
        // Glassmorphism on top of the .skeleton background-color
        background: `linear-gradient(
          90deg,
          var(--bg-elevated, #14141A) 25%,
          var(--bg-hover,    #1F1F2C) 50%,
          var(--bg-elevated, #14141A) 75%
        )`,
        backgroundSize: '200% 100%',
        // The shimmer pseudo-element from .skeleton handles the sweep animation.
        // Adding backdrop-filter for the glass feel beneath any overlapping content.
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
        border: '1px solid var(--border-subtle, rgba(255,255,255,0.04))',
        flexShrink: 0,
      }}
    />
  );
}

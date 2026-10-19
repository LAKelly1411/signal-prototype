const RADIUS = 7.5;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Donut of the score as a share of 100: 20% cobalt track, arc clockwise from 12 o'clock. */
export function RelevanceRing({ score }: { score: number }) {
  const arc = (CIRCUMFERENCE * Math.max(0, Math.min(score, 100))) / 100;
  return (
    <svg width={20} height={20} viewBox="0 0 20 20" aria-hidden="true" style={{ flexShrink: 0 }}>
      <circle cx={10} cy={10} r={RADIUS} fill="none" stroke="#004FFF" strokeOpacity={0.2} strokeWidth={5} />
      <circle
        cx={10} cy={10} r={RADIUS} fill="none" stroke="#004FFF" strokeWidth={5}
        strokeDasharray={`${arc.toFixed(2)} ${CIRCUMFERENCE.toFixed(2)}`}
        transform="rotate(-90 10 10)"
      />
    </svg>
  );
}

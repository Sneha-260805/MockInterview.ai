/**
 * ScoreCard — circular SVG gauge displaying a single score dimension.
 * Used on the FeedbackReport page.
 *
 * Props:
 *   label         – dimension name (e.g. "Technical")
 *   score         – integer 0-100
 *   subtitle      – small descriptive text below the label (optional)
 *   isPlaceholder – show an amber "placeholder" chip (for behavioral scores)
 */
export default function ScoreCard({ label, score, subtitle, isPlaceholder = false }) {
  const radius        = 38;
  const circumference = 2 * Math.PI * radius;
  const clamped       = Math.max(0, Math.min(100, score ?? 0));
  const offset        = circumference - (clamped / 100) * circumference;

  const strokeColor =
    clamped >= 70 ? "#22c55e" : clamped >= 50 ? "#eab308" : "#f97316";
  const bgRing =
    clamped >= 70
      ? "bg-green-50 border-green-100"
      : clamped >= 50
      ? "bg-yellow-50 border-yellow-100"
      : "bg-orange-50 border-orange-100";

  return (
    <div className={`flex flex-col items-center gap-3 p-5 rounded-2xl border ${bgRing}`}>
      {/* Circular gauge */}
      <div className="relative w-24 h-24">
        <svg
          viewBox="0 0 100 100"
          className="w-full h-full"
          style={{ transform: "rotate(-90deg)" }}
        >
          {/* Background track */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="8"
          />
          {/* Filled arc */}
          <circle
            cx="50" cy="50" r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.9s ease" }}
          />
        </svg>

        {/* Score number in the centre */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="text-2xl font-extrabold tabular-nums leading-none"
            style={{ color: strokeColor }}
          >
            {clamped}
          </span>
        </div>
      </div>

      {/* Label area */}
      <div className="text-center space-y-0.5">
        <p className="text-sm font-semibold text-gray-700">{label}</p>
        {subtitle && (
          <p className="text-xs text-gray-400">{subtitle}</p>
        )}
        {isPlaceholder && (
          <span className="inline-block mt-1 text-[10px] font-medium bg-amber-50 text-amber-600 border border-amber-200 rounded-full px-2 py-0.5">
            placeholder
          </span>
        )}
      </div>
    </div>
  );
}

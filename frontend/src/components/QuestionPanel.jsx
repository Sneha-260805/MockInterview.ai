const DIFFICULTY_STYLE = {
  easy:   { label: "Easy",   cls: "bg-green-100 text-green-700" },
  medium: { label: "Medium", cls: "bg-yellow-100 text-yellow-700" },
  hard:   { label: "Hard",   cls: "bg-red-100 text-red-700" },
};

export default function QuestionPanel({ question, index = 1 }) {
  if (!question) return null;

  const diff = DIFFICULTY_STYLE[question.difficulty] ?? DIFFICULTY_STYLE.easy;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-3">
          <span className="w-7 h-7 rounded-full bg-brand-500 text-white text-xs font-bold flex items-center justify-center">
            {index}
          </span>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            {question.topic}
          </span>
        </div>
        <span className={`text-xs font-semibold px-3 py-1 rounded-full ${diff.cls}`}>
          {diff.label}
        </span>
      </div>

      {/* Question text */}
      <div className="px-6 py-6">
        <p className="text-gray-900 text-lg leading-relaxed font-medium">
          {question.question}
        </p>
      </div>

      {/* Expected points */}
      {question.expected_points?.length > 0 && (
        <div className="px-6 pb-6">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Points to cover in your answer
          </p>
          <ul className="space-y-2">
            {question.expected_points.map((pt, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-gray-600">
                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-brand-400 shrink-0" />
                {pt}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

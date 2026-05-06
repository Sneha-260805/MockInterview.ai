export default function Dashboard() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <h2 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h2>
      <p className="text-gray-500 mb-8">
        Your interview sessions and progress will appear here.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {["Resume Upload", "Mock Interview", "Feedback Report"].map((title, i) => (
          <div
            key={i}
            className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm flex flex-col gap-2"
          >
            <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center text-brand-600 font-bold text-lg">
              {i + 1}
            </div>
            <h3 className="font-semibold text-gray-800">{title}</h3>
            <p className="text-sm text-gray-400">Coming soon</p>
          </div>
        ))}
      </div>
    </div>
  );
}

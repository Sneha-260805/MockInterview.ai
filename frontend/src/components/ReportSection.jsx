/**
 * ReportSection — a titled card wrapper used throughout FeedbackReport.jsx.
 *
 * Props:
 *   title     – section heading string
 *   icon      – JSX element rendered in a small box to the left of the title
 *   children  – content slot
 *   className – optional extra classes on the outer wrapper
 */
export default function ReportSection({ title, icon, children, className = "" }) {
  return (
    <div
      className={`bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-100 bg-gray-50">
        {icon && (
          <div className="w-7 h-7 rounded-lg bg-white border border-gray-200 flex items-center justify-center shrink-0">
            {icon}
          </div>
        )}
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      </div>

      {/* Content */}
      <div className="p-6">{children}</div>
    </div>
  );
}

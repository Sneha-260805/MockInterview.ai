import { Link, NavLink, useLocation } from "react-router-dom";
import { useState } from "react";

const NAV_LINKS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/upload", label: "Upload Resume" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // Hide navbar on the home page — it has its own full-page layout
  if (location.pathname === "/") return null;

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2 text-brand-600 font-bold text-base tracking-tight flex-shrink-0"
        >
          <span className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </span>
          <span>
            MockInterview
            <span className="text-gray-300 font-light">.ai</span>
          </span>
        </Link>

        {/* Desktop links */}
        <div className="hidden sm:flex items-center gap-1">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-600"
                    : "text-gray-500 hover:text-gray-900 hover:bg-gray-50"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
          <Link
            to="/upload"
            className="ml-2 px-4 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm"
          >
            Start Interview
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="sm:hidden p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition-colors"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="sm:hidden border-t border-gray-100 bg-white px-6 py-3 flex flex-col gap-1">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-600"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
          <Link
            to="/upload"
            onClick={() => setOpen(false)}
            className="mt-1 px-3 py-2 bg-brand-500 text-white rounded-lg text-sm font-semibold text-center"
          >
            Start Interview
          </Link>
        </div>
      )}
    </nav>
  );
}

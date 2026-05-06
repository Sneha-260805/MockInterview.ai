import { Link, NavLink } from "react-router-dom";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/upload", label: "Upload Resume" },
  { to: "/roles", label: "Role Recommendations" },
  { to: "/dashboard", label: "Dashboard" },
];

export default function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
      <Link to="/" className="text-brand-600 font-bold text-lg tracking-tight">
        MockInterview<span className="text-gray-400 font-light">.ai</span>
      </Link>
      <div className="flex gap-6">
        {navLinks.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `text-sm font-medium transition-colors ${
                isActive ? "text-brand-600" : "text-gray-500 hover:text-gray-900"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center text-center px-4">
      <p className="text-7xl font-extrabold text-brand-500">404</p>
      <h2 className="text-2xl font-bold text-gray-800 mt-4">Page not found</h2>
      <p className="text-gray-500 mt-2">
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/"
        className="mt-6 px-5 py-2.5 bg-brand-500 text-white rounded-lg font-medium hover:bg-brand-600 transition-colors"
      >
        Back to Home
      </Link>
    </div>
  );
}

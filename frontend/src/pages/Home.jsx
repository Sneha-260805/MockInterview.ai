import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import api from "../services/api";

export default function Home() {
  const [apiStatus, setApiStatus] = useState(null);

  useEffect(() => {
    api
      .get("/api/health")
      .then((res) => setApiStatus(res.data))
      .catch(() => setApiStatus({ status: "unreachable" }));
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-brand-50 to-white flex flex-col items-center justify-center px-4">
      <div className="max-w-2xl text-center space-y-6">
        <h1 className="text-5xl font-extrabold text-gray-900 leading-tight">
          Intelligent Mock{" "}
          <span className="text-brand-500">Interview Agent</span>
        </h1>
        <p className="text-lg text-gray-500">
          Practice real interview scenarios, get instant AI feedback, and land
          your dream job — all in one place.
        </p>

        <div className="flex gap-4 justify-center">
          <Link
            to="/dashboard"
            className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white rounded-xl font-semibold transition-colors shadow"
          >
            Get Started
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="px-6 py-3 border border-gray-300 hover:border-brand-500 rounded-xl font-semibold text-gray-700 hover:text-brand-600 transition-colors"
          >
            API Docs
          </a>
        </div>

        {apiStatus && (
          <p className="text-xs text-gray-400">
            API:{" "}
            <span
              className={
                apiStatus.status === "ok" ? "text-green-500" : "text-red-400"
              }
            >
              {apiStatus.status}
            </span>
            {apiStatus.storage && ` · storage: ${apiStatus.storage}`}
          </p>
        )}
      </div>
    </main>
  );
}

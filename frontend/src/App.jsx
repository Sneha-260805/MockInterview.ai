import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import ResumeUpload from "./pages/ResumeUpload";
import RoleRecommendation from "./pages/RoleRecommendation";
import InterviewRoom from "./pages/InterviewRoom";
import FeedbackReport from "./pages/FeedbackReport";
import JobRecommendation from "./pages/JobRecommendation";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/upload" element={<ResumeUpload />} />
        <Route path="/roles/:candidateId" element={<RoleRecommendation />} />
        <Route path="/roles" element={<RoleRecommendation />} />
        <Route path="/interview/:sessionId" element={<InterviewRoom />} />
        <Route path="/report/:sessionId" element={<FeedbackReport />} />
        <Route path="/jobs/:candidateId" element={<JobRecommendation />} />
        <Route path="/jobs" element={<JobRecommendation />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}

import api from "./api";

export async function startInterview(candidateId, selectedRole) {
  const response = await api.post("/api/interview/start", {
    candidate_id: candidateId,
    selected_role: selectedRole,
  });
  return response.data; // StartInterviewResponse
}

export async function getSession(sessionId) {
  const response = await api.get(`/api/interview/${sessionId}`);
  return response.data; // InterviewSession
}

export async function evaluateAnswer({ sessionId, questionId, question, answer, expectedPoints }) {
  const response = await api.post("/api/interview/evaluate-answer", {
    session_id: sessionId,
    question_id: questionId,
    question,
    answer,
    expected_points: expectedPoints,
  });
  return response.data; // EvaluationResult
}

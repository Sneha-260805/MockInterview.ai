import api from "./api";

export async function analyzeResume(candidateId, rawText) {
  const response = await api.post("/api/resume/analyze", {
    candidate_id: candidateId,
    raw_text: rawText,
  });
  return response.data; // { analysis, roles }
}

export async function getRoles(candidateId) {
  const response = await api.get(`/api/roles/${candidateId}`);
  return response.data; // RoleRecommendationResponse
}

import api from "./api";

/**
 * Fetch job recommendations for a candidate.
 * Returns JobRecommendationResponse:
 * { candidate_id, total_jobs_analyzed, recommended_jobs: [...] }
 */
export async function getJobRecommendations(candidateId) {
  const response = await api.get(`/api/jobs/${candidateId}`);
  return response.data;
}

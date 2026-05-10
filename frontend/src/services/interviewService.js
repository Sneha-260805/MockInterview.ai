import api from "./api";

const MEDIA_ANALYSIS_TIMEOUT_MS =
  Number(import.meta.env.VITE_MEDIA_ANALYSIS_TIMEOUT_MS) || 120000;

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

export async function generateFinalReport(sessionId) {
  const response = await api.post("/api/interview/final-report", {
    session_id: sessionId,
  });
  return response.data; // FinalReport
}

/**
 * Re-evaluate an improved answer for the same question (coaching loop retry).
 *
 * @param {Object} params
 * @param {string} params.sessionId
 * @param {string} params.questionId
 * @param {string} params.question
 * @param {string} params.improvedAnswer   - the candidate's improved text
 * @param {string[]} params.expectedPoints
 * @param {Object} params.previousEvaluation - EvaluationResult from first attempt
 * @param {number} params.attemptNumber     - 2 for first retry, 3 for second
 * @param {string} [params.topic]
 * @returns {Promise<ImprovedEvaluationResult>}
 */
export async function improveAnswer({
  sessionId,
  questionId,
  question,
  improvedAnswer,
  expectedPoints,
  previousEvaluation,
  attemptNumber = 2,
  topic,
}) {
  const response = await api.post("/api/interview/improve-answer", {
    session_id:           sessionId,
    question_id:          questionId,
    question,
    improved_answer:      improvedAnswer,
    expected_points:      expectedPoints,
    previous_evaluation:  previousEvaluation,
    attempt_number:       attemptNumber,
    topic,
  });
  return response.data; // ImprovedEvaluationResult
}

export async function nextQuestion({ sessionId, lastAnswerScore, confidenceScore, currentTopic }) {
  const response = await api.post("/api/interview/next-question", {
    session_id: sessionId,
    last_answer_score: lastAnswerScore,
    confidence_score: confidenceScore,
    current_topic: currentTopic,
  });
  return response.data; // NextQuestionResponse
}

/**
 * Upload an audio recording for transcription and behavioral scoring.
 * Optionally associates the result with a session + question number so
 * the final report can use real audio-derived scores.
 *
 * @param {Blob}   audioBlob      - audio Blob from MediaRecorder
 * @param {string} [sessionId]    - interview session ID
 * @param {number} [questionNumber] - 1-based question index
 * @returns {Promise<AudioAnalysisResponse>}
 */
/**
 * Upload a video clip or single frame for visual scoring.
 * Accepts any Blob; filename extension determines image vs video on backend.
 *
 * @param {Blob}   videoBlob      - webm clip or JPEG snapshot from MediaRecorder / canvas
 * @param {string} [filename]     - "frame.jpg" or "recording.webm" (sets Content-Type hint)
 * @param {string} [sessionId]
 * @param {number} [questionNumber]
 * @returns {Promise<VideoAnalysisResponse>}
 */
export async function analyzeVideo({ videoBlob, filename = "capture.webm", sessionId, questionNumber }) {
  const form = new FormData();
  form.append("video", videoBlob, filename);
  if (sessionId)              form.append("session_id",      sessionId);
  if (questionNumber != null) form.append("question_number", String(questionNumber));

  const response = await api.post("/api/scoring/video", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: MEDIA_ANALYSIS_TIMEOUT_MS,
  });
  return response.data; // VideoAnalysisResponse
}

export async function analyzeAudio({ audioBlob, sessionId, questionNumber }) {
  const form = new FormData();
  form.append("audio", audioBlob, "answer.webm");
  if (sessionId)      form.append("session_id",      sessionId);
  if (questionNumber != null) form.append("question_number", String(questionNumber));

  const response = await api.post("/api/scoring/audio", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: MEDIA_ANALYSIS_TIMEOUT_MS,
  });
  return response.data; // AudioAnalysisResponse
}

/**
 * Upload BOTH audio and video in a single request so the backend can
 * analyse them in parallel (asyncio.gather) instead of sequentially.
 *
 * This avoids the event-loop-blocking race condition that caused timeouts
 * when AudioRecorder and VideoRecorder each POSTed independently.
 *
 * @param {Blob}   audioBlob        - audio Blob from AudioRecorder
 * @param {Blob}   videoBlob        - video Blob or JPEG snapshot from VideoRecorder
 * @param {string} [videoFilename]  - "capture.webm" | "frame.jpg" etc.
 * @param {string} [sessionId]
 * @param {number} [questionNumber]
 * @returns {Promise<{ audio: AudioAnalysisResponse, video: VideoAnalysisResponse }>}
 */
export async function analyzeMediaCombined({
  audioBlob,
  videoBlob,
  videoFilename = "capture.webm",
  sessionId,
  questionNumber,
}) {
  const form = new FormData();
  form.append("audio", audioBlob, "answer.webm");
  form.append("video", videoBlob, videoFilename);
  if (sessionId)              form.append("session_id",      sessionId);
  if (questionNumber != null) form.append("question_number", String(questionNumber));

  const response = await api.post("/api/scoring/combined", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: MEDIA_ANALYSIS_TIMEOUT_MS,
  });
  return response.data; // { audio: AudioAnalysisResponse, video: VideoAnalysisResponse }
}

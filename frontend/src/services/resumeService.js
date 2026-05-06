import api from "./api";

export async function uploadResume(file) {
  const form = new FormData();
  form.append("file", file);

  const response = await api.post("/api/resume/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

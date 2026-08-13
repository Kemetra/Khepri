const language = document.body.dataset.language;
class ApiError extends Error {
  constructor(status) { super(String(status)); this.status = status; }
}
const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.status === 204 ? null : response.json();
};

const routeFor = (step) => `/beta/${language}/${step}`;
const resume = async () => {
  const current = document.body.dataset.step;
  try {
    const state = await api("/api/v1/beta/journey");
    if (state.step !== current) location.replace(routeFor(state.step));
    return state;
  } catch (error) {
    if (error.status === 401) {
      if (current !== "expired") location.replace(routeFor("expired"));
      return null;
    }
    throw error;
  }
};

const deleteContent = async () => {
  try {
    await api("/api/v1/beta/content", { method: "DELETE" });
  } catch (error) {
    if (error.status !== 503) throw error;
  }
  location.replace(`${routeFor("expired")}?deletion=requested`);
};

export { api, deleteContent, language, resume, routeFor };

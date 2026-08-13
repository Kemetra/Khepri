const language = document.body.dataset.language;
const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  if (!response.ok) throw new Error(String(response.status));
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
    if (current !== "expired") location.replace(routeFor("expired"));
    return null;
  }
};

const deleteContent = async () => {
  await api("/api/v1/beta/content", { method: "DELETE" });
  location.replace(routeFor("expired"));
};

export { api, deleteContent, language, resume, routeFor };

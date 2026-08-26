const language = document.body.dataset.language;
// The status alone cannot distinguish "your JSON was malformed" from a governed
// refusal naming the version pairing it refused. The server states its reason in
// `detail`, so the error carries it and the caller can show what was actually
// refused instead of a generic failure.
class ApiError extends Error {
  constructor(status, detail) { super(detail || String(status)); this.status = status; this.detail = detail || null; }
}
// A refused response is not necessarily JSON: a gateway can answer HTML and a 204
// has no body at all. So the read is guarded and a failure to parse leaves the
// detail null rather than replacing the status with a parser error.
const statedReason = async (response) => {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : null;
  } catch (error) {
    return null;
  }
};
const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  if (!response.ok) throw new ApiError(response.status, await statedReason(response));
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

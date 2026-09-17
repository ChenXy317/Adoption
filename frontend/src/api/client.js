const BASE = "";

export async function api(path, { method = "GET", body, signal } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { message: text };
  }
  if (!res.ok) {
    const error = new Error(data?.message || `请求失败 (${res.status})`);
    error.code = data?.code || "error";
    error.status = res.status;
    error.detail = data?.detail || "";
    throw error;
  }
  return data;
}

export const apiGet = (path, signal) => api(path, { signal });
export const apiPost = (path, body, signal) => api(path, { method: "POST", body, signal });
export const apiPatch = (path, body, signal) => api(path, { method: "PATCH", body, signal });
export const apiDelete = (path, signal) => api(path, { method: "DELETE", signal });

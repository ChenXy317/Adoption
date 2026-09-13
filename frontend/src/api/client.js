const BASE = "";

export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
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

export const apiGet = (path) => api(path);
export const apiPost = (path, body) => api(path, { method: "POST", body });
export const apiPatch = (path, body) => api(path, { method: "PATCH", body });
export const apiDelete = (path) => api(path, { method: "DELETE" });

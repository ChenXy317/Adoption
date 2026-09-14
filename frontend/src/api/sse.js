/**
 * SSE 流读取 — POST 对话并按事件分发。
 * handlers: { chunk, state_update, event_triggered, time_update, done, error }
 */
export async function streamChat(saveId, message, handlers = {}, signal) {
  const res = await fetch(`/api/saves/${saveId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!res.ok) {
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    const error = new Error(data?.message || `对话请求失败 (${res.status})`);
    error.code = data?.code || "error";
    throw error;
  }
  if (!res.body) {
    throw new Error("浏览器不支持流式读取");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = null;
  let dataLines = [];

  const dispatch = () => {
    if (!eventName) return;
    const raw = dataLines.join("\n");
    let payload = {};
    try {
      payload = raw ? JSON.parse(raw) : {};
    } catch {
      payload = {};
    }
    if (handlers[eventName]) handlers[eventName](payload);
    eventName = null;
    dataLines = [];
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).replace(/\r$/, "");
        buffer = buffer.slice(index + 1);
        if (line === "") {
          dispatch();
        } else if (line.startsWith("event: ")) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataLines.push(line.slice(6));
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
  dispatch();
}

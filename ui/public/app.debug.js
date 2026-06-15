// ================================================================================== debug tab
// Two tools for seeing what's really going on:
//  1) a LIVE event log — every SSE event this browser receives, appended as it arrives;
//  2) the FULL conversation — fetched from the server (which proxies OpenCode), including
//     thinking, every tool call's input/output, and the raw JSON of each message.
const DEBUG_LOG_MAX = 600;
function logDebugEvent(ev) {
  const pre = $("#debug-events");
  if (!pre) return;
  let line = "";
  try { line = JSON.stringify(ev); } catch (e) { line = String(ev); }
  if (line.length > 500) line = line.slice(0, 500) + "…";
  pre.appendChild(document.createTextNode(line + "\n"));
  while (pre.childNodes.length > DEBUG_LOG_MAX) pre.removeChild(pre.firstChild);
  const auto = $("#debug-autoscroll");
  if (!auto || auto.checked) pre.scrollTop = pre.scrollHeight;
}

async function loadDebugConvo() {
  const box = $("#debug-convo");
  if (!box) return;
  if (!sessionId) {
    box.innerHTML = '<div class="empty">No session yet — send a message first.</div>';
    return;
  }
  box.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const r = await fetch(`/api/session/${encodeURIComponent(sessionId)}/messages`);
    const data = await r.json();
    if (!r.ok) {
      box.innerHTML = `<div class="empty">⚠ ${escapeHtml((data && data.error) || ("HTTP " + r.status))}</div>`;
      return;
    }
    renderDebugConvo(box, Array.isArray(data) ? data : []);
  } catch (e) {
    box.innerHTML = `<div class="empty">⚠ ${escapeHtml(e.message || String(e))}</div>`;
  }
}

function renderDebugConvo(box, msgs) {
  if (!msgs.length) { box.innerHTML = '<div class="empty">No messages in this session.</div>'; return; }
  box.innerHTML = "";
  for (const m of msgs) {
    const info = m.info || m;             // OpenCode returns {info, parts}; tolerate flat too
    const parts = Array.isArray(m.parts) ? m.parts : [];
    const d = document.createElement("details");
    d.className = "dbg-msg " + (info.role === "user" ? "user" : "assistant");
    const when = info.time && info.time.created ? new Date(info.time.created).toLocaleTimeString() : "";
    const kinds = parts.map(p => p.type).filter(Boolean).join(" · ");
    const sum = document.createElement("summary");
    sum.innerHTML = `<b>${escapeHtml(info.role || "?")}</b> <span class="dbg-when">${escapeHtml(when)}</span> <em>${escapeHtml(kinds)}</em>`;
    d.appendChild(sum);
    for (const p of parts) {
      const pd = document.createElement("details");
      pd.className = "dbg-part";
      let label = p.type || "part", body = "";
      if (p.type === "text" || p.type === "reasoning") {
        body = p.text || "";
        if (p.type === "reasoning") label = "reasoning 💭";
      } else if (p.type === "tool") {
        const st = p.state || {};
        label = `tool: ${p.tool || "?"} (${st.status || "?"})`;
        body = "input:\n" + JSON.stringify(st.input || {}, null, 2) +
               (st.output ? "\n\noutput:\n" + String(st.output) : "") +
               (st.error ? "\n\nerror:\n" + String(st.error) : "");
      } else {
        body = JSON.stringify(p, null, 2);
      }
      pd.innerHTML = `<summary>${escapeHtml(label)}</summary>`;
      const pre = document.createElement("pre");
      pre.textContent = body;
      pd.appendChild(pre);
      d.appendChild(pd);
    }
    const raw = document.createElement("details");
    raw.className = "dbg-part raw";
    raw.innerHTML = "<summary>raw json</summary>";
    const rp = document.createElement("pre");
    try { rp.textContent = JSON.stringify(m, null, 2); } catch (e) { rp.textContent = String(m); }
    raw.appendChild(rp);
    d.appendChild(raw);
    box.appendChild(d);
  }
}

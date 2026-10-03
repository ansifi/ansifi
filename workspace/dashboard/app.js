const state = {
  notes: "",
  course: "",
  platforms: [
    { id: "linkedin", label: "LinkedIn", compose: "https://www.linkedin.com/feed/" },
    { id: "devto", label: "Dev.to", compose: "https://dev.to/new" },
    { id: "medium", label: "Medium", compose: "https://medium.com/new-story" },
    { id: "x", label: "X / Twitter", compose: "https://twitter.com/compose/tweet" },
    { id: "hashnode", label: "Hashnode", compose: "https://hashnode.com/draft" },
  ],
};

function showStep(n) {
  const id = String(n) === "stories" ? "step-stories" : `step-${n}`;
  document.querySelectorAll(".panel").forEach((el) => {
    el.hidden = el.id !== id;
  });
  document.querySelectorAll(".step").forEach((btn) => {
    btn.classList.toggle("is-on", btn.dataset.step === String(n));
  });
}

document.querySelectorAll(".step").forEach((btn) => {
  btn.addEventListener("click", () => showStep(btn.dataset.step));
});

function formatFor(id, markdown) {
  const raw = String(markdown || "");
  if (id === "x") {
    const line = raw.replace(/[#*_`]/g, "").split("\n").map((s) => s.trim()).filter(Boolean)[0] || "";
    return line.slice(0, 240);
  }
  if (id === "linkedin") {
    return raw.replace(/^#{1,6}\s+/gm, "").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").trim();
  }
  return raw;
}

function renderPlatforms() {
  const box = document.getElementById("platforms");
  box.innerHTML = "";
  state.platforms.forEach((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "platform";
    b.textContent = `Copy for ${p.label}`;
    b.addEventListener("click", async () => {
      const source = document.getElementById("post-source").value;
      const text = formatFor(p.id, source === "notes" ? state.notes : state.course);
      await navigator.clipboard.writeText(text);
      window.open(p.compose, "_blank", "noopener");
      const st = document.getElementById("post-status");
      st.hidden = false;
      st.textContent = `Copied for ${p.label}. Paste into the tab that opened. Online send comes later.`;
    });
    box.appendChild(b);
  });
}

document.getElementById("analyze-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const btn = document.getElementById("analyze-btn");
  const status = document.getElementById("analyze-status");
  btn.disabled = true;
  status.hidden = false;
  status.textContent = "Analysing… if Ollama is down, a teaching template is still saved.";
  const body = {
    kind: form.kind.value,
    title: form.title.value,
    path: form.path.value,
    description: form.description.value,
  };
  try {
    const res = await fetch("/apps/coding-api/api/skills/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || res.statusText);
    state.notes = data.notes || "";
    state.course = data.course || "";
    if (Array.isArray(data.platforms) && data.platforms.length) state.platforms = data.platforms;
    document.getElementById("notes").value = state.notes;
    document.getElementById("course").value = state.course;
    document.getElementById("saved-paths").textContent =
      `Saved ${data.note_path || ""} and ${data.course_path || ""}. Draft: ${data.draft_path || ""}.` +
      (data.used_agent ? " Agent used." : " Template used (start Ollama for a live analysis).");
    renderPlatforms();
    showStep(2);
  } catch (err) {
    status.textContent = String(err.message || err);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("notes").addEventListener("input", (e) => {
  state.notes = e.target.value;
});
document.getElementById("course").addEventListener("input", (e) => {
  state.course = e.target.value;
});
document.getElementById("to-post").addEventListener("click", () => showStep(3));

renderPlatforms();

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showStory(row) {
  const detail = document.getElementById("story-detail");
  if (!detail || !row) return;
  detail.hidden = false;
  document.getElementById("story-title").textContent = row.title || "Story";
  document.getElementById("story-meta").textContent =
    (row.status || "draft") +
    " · " +
    Number(row.views || 0) +
    " views · " +
    Number(row.responses || 0) +
    " replies" +
    (row.source_url ? " · " + row.source_url : "");
  document.getElementById("story-body").textContent = row.body || "";
}

async function loadStories(focusId) {
  const list = document.getElementById("story-list");
  if (!list) return;
  list.textContent = "Loading stories…";
  try {
    const res = await fetch("/api/ai/stories", { credentials: "same-origin" });
    const data = await res.json();
    const posts = (data && data.posts) || [];
    if (!posts.length) {
      list.innerHTML = "<p class=\"muted\">No stories on this desk yet.</p>";
      return;
    }
    list.innerHTML = posts
      .map((row) => {
        return (
          '<button type="button" class="story-row" data-id="' +
          escapeHtml(String(row.id)) +
          '"><strong>' +
          escapeHtml(row.title || "Story") +
          "</strong><span>" +
          Number(row.views || 0) +
          " views · " +
          escapeHtml(row.status || "draft") +
          "</span></button>"
        );
      })
      .join("");
    list.querySelectorAll(".story-row").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = posts.find((p) => String(p.id) === btn.getAttribute("data-id"));
        showStory(row);
      });
    });
    const wanted = posts.find((p) => String(p.id) === String(focusId)) || posts[0];
    showStory(wanted);
  } catch (err) {
    list.textContent = String(err.message || err);
  }
}

const params = new URLSearchParams(location.search);
if (params.get("view") === "stories") {
  showStep("stories");
  loadStories(params.get("post"));
}

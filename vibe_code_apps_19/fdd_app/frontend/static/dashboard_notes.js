(function () {
  const pageId = window.DASHBOARD_PAGE || "index";
  const listEl = document.getElementById("notes-post-list");
  const draftEl = document.getElementById("notes-draft");
  const postBtn = document.getElementById("btn-post-note");
  const section = document.getElementById("page-notes-section");
  if (!listEl || !section) return;

  function canEdit() {
    return !window.DASHBOARD_SESSION || window.DASHBOARD_SESSION.can_edit !== false;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function renderPosts(posts) {
    listEl.innerHTML = "";
    if (!posts || !posts.length) {
      listEl.innerHTML = '<p class="note notes-empty">No notes yet — add your first finding below.</p>';
      return;
    }
    posts.forEach((p) => {
      const card = document.createElement("article");
      card.className = "note-post";
      card.dataset.id = p.id;
      const meta = [p.ts, p.author].filter(Boolean).join(" · ");
      card.innerHTML = `
        <header class="note-post-head">
          <time>${esc(meta || "Posted")}</time>
          ${canEdit() ? `<button type="button" class="btn note-delete" data-id="${esc(p.id)}">Delete</button>` : ""}
        </header>
        <div class="note-post-body">${esc(p.text).replace(/\n/g, "<br/>")}</div>
      `;
      listEl.appendChild(card);
    });
    listEl.querySelectorAll(".note-delete").forEach((b) => {
      b.addEventListener("click", () => deletePost(b.dataset.id));
    });
  }

  async function loadPosts() {
    const res = await fetch(`/api/config?page=${pageId}`);
    const data = await res.json();
    window.DASHBOARD_SESSION = { ...window.DASHBOARD_SESSION, ...data };
    renderPosts(data.page_notes || []);
    if (draftEl && !canEdit()) {
      draftEl.disabled = true;
      if (postBtn) postBtn.disabled = true;
    }
  }

  async function deletePost(postId) {
    if (!canEdit() || !postId) return;
    if (!confirm("Delete this note?")) return;
    const res = await fetch("/api/notes/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page: pageId, action: "delete", post_id: postId }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Delete failed");
      return;
    }
    renderPosts(data.posts || []);
  }

  async function postNote() {
    if (!canEdit() || !draftEl) return;
    const text = draftEl.value.trim();
    if (!text) return;
    if (postBtn) postBtn.disabled = true;
    try {
      const res = await fetch("/api/notes/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page: pageId, action: "add", text }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Post failed");
      draftEl.value = "";
      renderPosts(data.posts || []);
    } catch (e) {
      alert(String(e.message || e));
    } finally {
      if (postBtn) postBtn.disabled = false;
    }
  }

  if (postBtn) postBtn.addEventListener("click", postNote);
  if (draftEl) {
    draftEl.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") postNote();
    });
  }

  window.renderPageNotes = renderPosts;
  loadPosts();
})();

(() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file");
  const previewWrap = document.getElementById("preview-wrap");
  const preview = document.getElementById("preview");
  const meta = document.getElementById("meta");
  const form = document.getElementById("edit-form");
  const generateBtn = document.getElementById("generate-btn");
  const statusEl = document.getElementById("status");
  const galleryEl = document.getElementById("gallery");
  const bri = form.elements.brightness;
  const con = form.elements.contrast;
  const briVal = document.getElementById("bri-val");
  const conVal = document.getElementById("con-val");

  let sourceId = null;

  function setStatus(msg, isErr = false) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("err", !!isErr);
  }

  bri.addEventListener("input", () => {
    briVal.textContent = Number(bri.value).toFixed(2);
  });
  con.addEventListener("input", () => {
    conVal.textContent = Number(con.value).toFixed(2);
  });

  function openPicker() {
    fileInput.click();
  }
  dropzone.addEventListener("click", openPicker);
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  });

  ["dragenter", "dragover"].forEach((ev) => {
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.add("drag");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag");
    });
  });
  dropzone.addEventListener("drop", (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f) uploadFile(f);
  });
  fileInput.addEventListener("change", () => {
    const f = fileInput.files?.[0];
    if (f) uploadFile(f);
  });

  async function uploadFile(file) {
    setStatus("Uploading…");
    generateBtn.disabled = true;
    sourceId = null;
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch("/api/upload", { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      sourceId = data.id;
      preview.src = data.url + "?t=" + Date.now();
      previewWrap.classList.remove("hidden");
      meta.textContent = `${data.width}×${data.height} · ${data.format} · id ${data.id}`;
      generateBtn.disabled = false;
      setStatus("Ready — adjust edits, then Generate.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!sourceId) {
      setStatus("Upload an image first.", true);
      return;
    }
    generateBtn.disabled = true;
    setStatus("Generating on CPU…");
    const body = new FormData();
    body.append("source_id", sourceId);
    body.append("crop", form.elements.crop.value.trim());
    body.append("max_width", form.elements.max_width.value || "0");
    body.append("brightness", form.elements.brightness.value);
    body.append("contrast", form.elements.contrast.value);
    body.append("filter", form.elements.filter.value);
    try {
      const res = await fetch("/api/generate", { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Generate failed");
      setStatus("Done — see gallery below.");
      await loadGallery();
    } catch (err) {
      setStatus(err.message || String(err), true);
    } finally {
      generateBtn.disabled = !sourceId;
    }
  });

  async function loadGallery() {
    try {
      const res = await fetch("/api/gallery");
      const data = await res.json();
      const items = data.items || [];
      if (!items.length) {
        galleryEl.innerHTML = "<p class='hint'>No results yet.</p>";
        return;
      }
      galleryEl.innerHTML = items
        .map(
          (it) => `
        <article class="pair">
          <div class="row">
            <img src="${it.before}" alt="Before" />
            <img src="${it.after}" alt="After" />
          </div>
          <div class="cap">
            <div><strong>${it.label || "AI-assisted / transformed (CPU)"}</strong></div>
            <div>${it.created || ""} · <a href="${it.after}" download>Download</a></div>
          </div>
        </article>`
        )
        .join("");
    } catch {
      galleryEl.innerHTML = "<p class='hint'>Could not load gallery.</p>";
    }
  }

  loadGallery();
})();

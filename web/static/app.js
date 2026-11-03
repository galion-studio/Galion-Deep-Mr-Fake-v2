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
  let sourceIds = [];

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
    const list = e.dataTransfer?.files;
    if (list && list.length) uploadFiles(list);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files?.length) uploadFiles(fileInput.files);
  });

  async function uploadFiles(fileList) {
    const files = Array.from(fileList || []).filter(Boolean);
    fileInput.value = "";
    if (!files.length) return;
    setStatus(files.length > 1 ? `Uploading ${files.length} images…` : "Uploading…");
    generateBtn.disabled = true;
    sourceId = null;
    sourceIds = [];
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    try {
      const res = await fetch("/api/upload", { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      const items = data.items || (data.id ? [data] : []);
      sourceIds = items.map((item) => item.id).filter(Boolean);
      sourceId = sourceIds[0] || null;
      const first = items[0];
      if (first) {
        preview.src = first.url + "?t=" + Date.now();
        previewWrap.classList.remove("hidden");
        const idText = sourceIds.join(", ");
        meta.textContent =
          items.length > 1
            ? `${items.length} images · first ${first.width}×${first.height} · ids ${idText}`
            : `${first.width}×${first.height} · ${first.format} · id ${first.id}`;
      }
      refreshGenerateEnabled();
      setStatus(
        items.length > 1
          ? `Ready — ${items.length} images. Adjust edits, then Generate.`
          : "Ready — adjust edits, then Generate."
      );
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const ids = batchIds();
    if (!ids.length) {
      setStatus("Upload an image, or paste already-uploaded ids.", true);
      return;
    }
    generateBtn.disabled = true;
    setStatus(ids.length > 1 ? `Generating ${ids.length} images on CPU…` : "Generating on CPU…");
    const body = new FormData();
    body.append("source_ids", ids.join(","));
    body.append("source_id", ids[0]);
    body.append("preset", form.elements.preset.value);
    body.append("crop", form.elements.crop.value.trim());
    body.append("max_width", form.elements.max_width.value || "0");
    body.append("brightness", form.elements.brightness.value);
    body.append("contrast", form.elements.contrast.value);
    body.append("saturation", form.elements.saturation.value);
    body.append("sharpness", form.elements.sharpness.value);
    body.append("rotate", form.elements.rotate.value || "0");
    body.append("flip", form.elements.flip.value);
    body.append("filter", form.elements.filter.value);
    body.append("posterize", form.elements.posterize.value || "0");
    body.append("solarize", form.elements.solarize.value || "0");
    body.append("blur_radius", form.elements.blur_radius.value || "0");
    body.append("colorize_black", form.elements.colorize_black.value.trim());
    body.append("colorize_white", form.elements.colorize_white.value.trim());
    body.append("invert", form.elements.invert.checked ? "1" : "0");
    body.append("equalize", form.elements.equalize.checked ? "1" : "0");
    try {
      const res = await fetch("/api/generate", { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Generate failed");
      const n = data.count || (data.items ? data.items.length : 1);
      const failed = (data.errors || []).length;
      setStatus(
        failed
          ? `Done — ${n} result${n === 1 ? "" : "s"}, ${failed} failed.`
          : n > 1
            ? `Done — ${n} results in the gallery.`
            : "Done — see gallery below."
      );
      await loadGallery();
    } catch (err) {
      setStatus(err.message || String(err), true);
    } finally {
      refreshGenerateEnabled();
    }
  });

  /* ws-ops: preset bundles + batch id field. Server remains the source of preset values. */
  const WS_ADJUST = [
    "brightness",
    "contrast",
    "saturation",
    "sharpness",
    "rotate",
    "flip",
    "filter",
    "posterize",
    "solarize",
    "invert",
    "equalize",
    "colorize_black",
    "colorize_white",
    "blur_radius",
  ];
  const presetSelect = document.getElementById("ws-preset");
  const presetHelp = document.getElementById("ws-preset-help");
  const batchInput = document.getElementById("ws-source-ids");
  const sat = form.elements.saturation;
  const shp = form.elements.sharpness;
  const satVal = document.getElementById("ws-sat-val");
  const shpVal = document.getElementById("ws-shp-val");
  let wsDefaults = {};
  let wsPresets = [];

  function batchIds() {
    const typed = (batchInput?.value || "").trim();
    if (typed) {
      return typed.split(",").map((part) => part.trim()).filter(Boolean);
    }
    return sourceIds.slice();
  }

  function refreshGenerateEnabled() {
    generateBtn.disabled = batchIds().length === 0;
  }

  sat.addEventListener("input", () => {
    satVal.textContent = Number(sat.value).toFixed(2);
  });
  shp.addEventListener("input", () => {
    shpVal.textContent = Number(shp.value).toFixed(2);
  });
  batchInput.addEventListener("input", refreshGenerateEnabled);

  function setField(name, value) {
    const el = form.elements[name];
    if (!el) return;
    if (el.type === "checkbox") {
      el.checked = value === true || value === 1 || value === "1";
    } else if (value === null || value === undefined) {
      el.value = "";
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function applyPresetBundle(params) {
    WS_ADJUST.forEach((key) => {
      const has = Object.prototype.hasOwnProperty.call(params, key);
      setField(key, has ? params[key] : wsDefaults[key]);
    });
  }

  presetSelect.addEventListener("change", () => {
    const chosen = wsPresets.find((item) => item.id === presetSelect.value);
    presetHelp.textContent = chosen
      ? chosen.description
      : "Custom settings. A preset fills the edit bundle; you can still tweak a control after.";
    applyPresetBundle(chosen ? chosen.params : {});
  });

  async function loadPresets() {
    try {
      const res = await fetch("/api/presets");
      const data = await res.json();
      if (!res.ok) return;
      wsDefaults = data.defaults || {};
      wsPresets = data.presets || [];
      wsPresets.forEach((item) => {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.label || item.id;
        presetSelect.appendChild(opt);
      });
      presetHelp.textContent =
        "Custom settings. A preset fills the edit bundle; you can still tweak a control after.";
    } catch {
      presetHelp.textContent = "Presets unavailable — manual edits still work.";
    }
  }

  loadPresets();

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

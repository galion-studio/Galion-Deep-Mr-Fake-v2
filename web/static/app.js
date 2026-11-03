(() => {
  const MAX_BYTES = 12 * 1024 * 1024;
  const MAX_BATCH = 16;
  const ALLOWED_EXT = new Set(["jpg", "jpeg", "png", "webp"]);
  const ALLOWED_MIME = new Set([
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/x-png",
    "image/webp",
    "application/octet-stream",
  ]);

  const dropzone = document.getElementById("dropzone");
  const dropTitle = document.getElementById("drop-title");
  const dropSpinner = document.getElementById("drop-spinner");
  const fileInput = document.getElementById("file");
  const previewWrap = document.getElementById("preview-wrap");
  const preview = document.getElementById("preview");
  const meta = document.getElementById("meta");
  const form = document.getElementById("edit-form");
  const generateBtn = document.getElementById("generate-btn");
  const generateSpinner = generateBtn.querySelector(".spinner");
  const generateLabel = generateBtn.querySelector(".btn-label");
  const resetBtn = document.getElementById("reset-btn");
  const formHint = document.getElementById("form-hint");
  const toast = document.getElementById("toast");
  const galleryEl = document.getElementById("gallery");
  const bri = form.elements.brightness;
  const con = form.elements.contrast;
  const sat = form.elements.saturation;
  const shp = form.elements.sharpness;
  const briVal = document.getElementById("bri-val");
  const conVal = document.getElementById("con-val");
  const satVal = document.getElementById("ws-sat-val");
  const shpVal = document.getElementById("ws-shp-val");
  const presetSelect = document.getElementById("ws-preset");
  const presetHelp = document.getElementById("ws-preset-help");
  const batchInput = document.getElementById("ws-source-ids");

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

  let sourceId = null;
  let sourceIds = [];
  let uploading = false;
  let generating = false;
  let toastTimer = 0;
  let wsDefaults = {};
  let wsPresets = [];

  const EMPTY_COPY =
    "Drop a photo and press Generate. Before and after pairs show up here, labelled AI-assisted / transformed (CPU).";
  const CUSTOM_HELP =
    "Custom settings. A preset fills the edit bundle; you can still tweak a control after.";

  function setHint(text) {
    formHint.textContent = text;
  }

  function setStatus(message, kind = "info") {
    window.clearTimeout(toastTimer);
    toast.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
    toast.classList.remove("success", "error", "info", "progress", "is-empty");
    if (!message) {
      toast.classList.add("is-empty");
      toast.replaceChildren();
      return;
    }
    toast.classList.add(kind);
    const text = document.createElement("p");
    text.className = "toast-text";
    text.textContent = message;
    toast.replaceChildren(text);
    if (kind === "error") {
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "dismiss";
      dismiss.textContent = "Dismiss";
      dismiss.addEventListener("click", () => setStatus(""));
      toast.append(dismiss);
    }
    if (kind === "success") toastTimer = window.setTimeout(() => setStatus(""), 4500);
    if (kind === "info") toastTimer = window.setTimeout(() => setStatus(""), 5000);
  }

  function syncSliders() {
    const pairs = [
      [bri, briVal],
      [con, conVal],
      [sat, satVal],
      [shp, shpVal],
    ];
    pairs.forEach(([input, label]) => {
      const value = Number(input.value);
      const shown = Number.isFinite(value) ? value.toFixed(2) : input.value;
      label.textContent = shown;
      input.setAttribute("aria-valuenow", String(value));
      input.setAttribute("aria-valuetext", shown);
    });
  }

  function setDropTitle(busyText) {
    dropTitle.replaceChildren();
    if (busyText) {
      dropTitle.textContent = busyText;
      return;
    }
    dropTitle.append("Drop photos here, or ");
    const browse = document.createElement("span");
    browse.className = "link";
    browse.textContent = "browse";
    dropTitle.append(browse);
  }

  function batchIds() {
    const typed = (batchInput.value || "").trim();
    if (typed) {
      return typed
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
    }
    return sourceIds.slice();
  }

  function syncControls() {
    const busy = uploading || generating;
    dropzone.classList.toggle("is-busy", busy);
    dropzone.setAttribute("aria-busy", uploading ? "true" : "false");
    dropzone.setAttribute("aria-disabled", busy ? "true" : "false");
    fileInput.disabled = busy;
    dropSpinner.hidden = !uploading;
    generateBtn.disabled = busy || batchIds().length === 0;
    generateBtn.setAttribute("aria-busy", generating ? "true" : "false");
    generateSpinner.hidden = !generating;
    generateLabel.textContent = generating ? "Generating…" : "Generate";
    resetBtn.disabled = busy;
    for (const el of form.querySelectorAll("input, select")) el.disabled = busy;
    if (!uploading) setDropTitle("");
  }

  function clearInvalid() {
    for (const el of form.querySelectorAll("[aria-invalid='true']")) el.removeAttribute("aria-invalid");
  }

  function revealField(field) {
    if (!field) return;
    const details = field.closest("details");
    if (details) details.open = true;
    window.requestAnimationFrame(() => {
      field.focus();
      field.scrollIntoView({ block: "nearest" });
    });
  }

  function extensionOf(name) {
    const parts = String(name || "").toLowerCase().split(".");
    return parts.length > 1 ? parts.pop() : "";
  }

  function fileProblem(file) {
    if (!file) return "Choose a JPEG, PNG, or WebP image to upload (max 12 MB each).";
    const name = file.name || "that file";
    const ext = extensionOf(name);
    const type = (file.type || "").toLowerCase();
    const extOk = ALLOWED_EXT.has(ext);
    const typeOk = !type || ALLOWED_MIME.has(type);
    if (!extOk || !typeOk) {
      const shown = type && !ALLOWED_MIME.has(type) ? type : ext ? `.${ext}` : "an unknown type";
      return `"${name}" is ${shown}. Upload a JPEG, PNG, or WebP (max 12 MB each).`;
    }
    if (!file.size) return `"${name}" is empty. Choose an image that contains data.`;
    if (file.size > MAX_BYTES) {
      const mb = file.size / (1024 * 1024);
      const shown = mb >= 12.05 ? `${mb.toFixed(1)} MB` : "just over 12 MB";
      return `"${name}" is ${shown}. The limit is 12 MB each — choose a smaller JPEG, PNG, or WebP.`;
    }
    return "";
  }

  function filesProblem(files) {
    if (!files.length) return "Choose one or more JPEG, PNG, or WebP images (max 12 MB each).";
    if (files.length > MAX_BATCH) {
      return `Batch limit is ${MAX_BATCH} images. Choose fewer files and try again.`;
    }
    for (const file of files) {
      const problem = fileProblem(file);
      if (problem) return problem;
    }
    return "";
  }

  function cropProblem(value) {
    if (!value) return "";
    const parts = value.split(",").map((part) => part.trim());
    if (parts.length !== 4 || parts.some((part) => !/^\d+$/.test(part))) {
      return "Crop must be four whole numbers: x, y, width, height (pixels). Example: 10, 10, 400, 300. Leave it blank to keep the full image.";
    }
    if (Number(parts[2]) < 1 || Number(parts[3]) < 1) return "Crop width and height must be at least 1 pixel.";
    if (parts.some((part) => Number(part) > 100000)) return "Crop values must be 100000 pixels or less.";
    return "";
  }

  function wholeNumberProblem(raw, label, max, zeroHint) {
    const text = String(raw ?? "").trim();
    if (!text) return "";
    if (!/^\d+$/.test(text) || Number(text) > max) {
      return `${label} must be a whole number from 0 to ${max}. ${zeroHint}`;
    }
    return "";
  }

  function decimalProblem(raw, label, min, max) {
    const text = String(raw ?? "").trim();
    if (!text) return "";
    if (!/^-?\d+(\.\d+)?$/.test(text)) return `${label} must be a number from ${min} to ${max}.`;
    const value = Number(text);
    if (value < min || value > max) return `${label} must be between ${min} and ${max}.`;
    return "";
  }

  function colorProblem(value, label) {
    const text = value.trim();
    if (!text) return "";
    if (!/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(text)) {
      return `${label} must be a hex color like #0d1b2a, or left blank.`;
    }
    return "";
  }

  function batchProblem(raw) {
    const text = raw.trim();
    if (!text) return "";
    const ids = text
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    if (ids.length > MAX_BATCH) return `Batch limit is ${MAX_BATCH} images. Remove some ids and try again.`;
    const bad = ids.find((id) => !/^[a-f0-9]{12}$/.test(id));
    if (bad) return `"${bad}" is not a valid image id. Use 12-character ids from an upload, separated by commas.`;
    return "";
  }

  function validateForm() {
    clearInvalid();
    const ids = batchIds();
    if (!ids.length) {
      return {
        message: "Upload a JPEG, PNG, or WebP, or paste already-uploaded ids, before generating.",
        field: batchInput,
      };
    }
    const typed = batchProblem(batchInput.value);
    if (typed) return { message: typed, field: batchInput };
    const cropMsg = cropProblem(form.elements.crop.value.trim());
    if (cropMsg) return { message: cropMsg, field: form.elements.crop };
    const widthMsg = wholeNumberProblem(
      form.elements.max_width.value,
      "Max width",
      4096,
      "Use 0 to keep the original width.",
    );
    if (widthMsg) return { message: widthMsg, field: form.elements.max_width };
    const rotateMsg = decimalProblem(form.elements.rotate.value, "Rotate", -360, 360);
    if (rotateMsg) return { message: rotateMsg, field: form.elements.rotate };
    const blurMsg = decimalProblem(form.elements.blur_radius.value, "Blur radius", 0, 30);
    if (blurMsg) return { message: blurMsg, field: form.elements.blur_radius };
    const posterMsg = wholeNumberProblem(form.elements.posterize.value, "Posterize bits", 8, "Use 0 to turn it off.");
    if (posterMsg) return { message: posterMsg, field: form.elements.posterize };
    const solarMsg = wholeNumberProblem(form.elements.solarize.value, "Solarize", 255, "Use 0 to turn it off.");
    if (solarMsg) return { message: solarMsg, field: form.elements.solarize };
    const blackMsg = colorProblem(form.elements.colorize_black.value, "Colorize black");
    if (blackMsg) return { message: blackMsg, field: form.elements.colorize_black };
    const whiteMsg = colorProblem(form.elements.colorize_white.value, "Colorize white");
    if (whiteMsg) return { message: whiteMsg, field: form.elements.colorize_white };
    return null;
  }

  function messageFromResponse(res, data, raw) {
    const detail = data && data.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((part) => part !== "body" && part !== "query" && part !== "path").join(" ")
            : "";
          return loc ? `${loc}: ${item.msg || "invalid value"}` : item.msg || "Invalid request.";
        }
        return "Invalid request.";
      });
      const text = parts.filter(Boolean).join(" ");
      if (text) return text;
    }
    if (res.status === 413) return "That file is too large. The limit is 12 MB each.";
    if (res.status === 404) return "That source image was not found. Upload it again, then generate.";
    if (res.status >= 500) return "The server had a problem processing that request. Try again in a moment.";
    const snippet = (raw || "").replace(/\s+/g, " ").trim().slice(0, 180);
    if (snippet && !snippet.startsWith("<")) return snippet;
    return `Request failed (${res.status}). Try again.`;
  }

  async function postForm(url, body) {
    let res;
    try {
      res = await fetch(url, { method: "POST", body });
    } catch {
      throw new Error("Could not reach the server. Check your connection and try again.");
    }
    const raw = await res.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = null;
      }
    }
    if (!res.ok) throw new Error(messageFromResponse(res, data, raw));
    if (!data || typeof data !== "object") throw new Error("The server returned an unexpected response. Try again.");
    return data;
  }

  function safeMediaUrl(url) {
    return typeof url === "string" && /^\/media\/(uploads|outputs)\/[A-Za-z0-9._-]+$/.test(url) ? url : "";
  }

  function renderMessage(title, copy, isError) {
    galleryEl.replaceChildren();
    const wrap = document.createElement("div");
    wrap.className = isError ? "empty is-error" : "empty";
    const heading = document.createElement("p");
    heading.className = "empty-title";
    heading.textContent = title;
    const text = document.createElement("p");
    text.className = "empty-copy";
    text.textContent = copy;
    wrap.append(heading, text);
    galleryEl.append(wrap);
  }

  function figure(url, caption, alt) {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    if (url) img.src = url;
    img.alt = alt;
    const cap = document.createElement("figcaption");
    cap.textContent = caption;
    fig.append(img, cap);
    return fig;
  }

  function paramsLine(params) {
    if (!params || typeof params !== "object") return "";
    const bits = [];
    if (params.crop) bits.push("cropped");
    if (params.max_width) bits.push(`max ${params.max_width}px`);
    if (params.rotate) bits.push(`rotate ${params.rotate}°`);
    if (params.flip && params.flip !== "none") bits.push(`flip ${params.flip}`);
    if (params.filter && params.filter !== "none") bits.push(String(params.filter));
    return bits.join(" · ");
  }

  function renderItem(item) {
    const before = safeMediaUrl(item.before);
    const after = safeMediaUrl(item.after);
    const article = document.createElement("article");
    article.className = "pair";
    if (item.ai_generated) article.dataset.aiGenerated = "true";
    const row = document.createElement("div");
    row.className = "row";
    row.append(figure(before, "Before", "Before, original upload"), figure(after, "After", "After, AI-assisted transformed result"));
    const cap = document.createElement("div");
    cap.className = "cap";
    const label = document.createElement("div");
    if (item.ai_generated) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "AI-generated";
      label.append(badge);
    }
    const strong = document.createElement("strong");
    strong.textContent = item.label || "AI-assisted / transformed (CPU)";
    label.append(strong);
    const details = document.createElement("div");
    const lead = [];
    if (item.created) lead.push(item.created);
    if (item.consent_attested === true) lead.push("consent attested");
    else if (item.consent_attested === false) lead.push("consent not attested");
    if (lead.length) details.append(`${lead.join(" · ")} · `);
    if (after) {
      const link = document.createElement("a");
      link.href = after;
      link.download = "";
      link.textContent = "Download result";
      details.append(link);
    } else {
      details.append("Result file is unavailable.");
    }
    const metaUrl = safeMediaUrl(item.meta);
    if (metaUrl) {
      details.append(document.createTextNode(" · "));
      const sidecar = document.createElement("a");
      sidecar.href = metaUrl;
      sidecar.textContent = "Sidecar";
      details.append(sidecar);
    }
    cap.append(label, details);
    const summary = paramsLine(item.params);
    if (summary) {
      const extra = document.createElement("div");
      extra.className = "params";
      extra.textContent = summary;
      cap.append(extra);
    }
    article.append(row, cap);
    return article;
  }

  async function loadGallery() {
    galleryEl.setAttribute("aria-busy", "true");
    try {
      let res;
      try {
        res = await fetch("/api/gallery");
      } catch {
        renderMessage("Gallery unavailable", "Could not reach the server. Check your connection and refresh the page.", true);
        return;
      }
      const raw = await res.text();
      let data = null;
      if (raw) {
        try {
          data = JSON.parse(raw);
        } catch {
          data = null;
        }
      }
      if (!res.ok || !data || !Array.isArray(data.items)) {
        const detail = data && typeof data.detail === "string" ? data.detail : "";
        renderMessage("Gallery unavailable", detail || "The gallery could not be loaded. Refresh the page to try again.", true);
        return;
      }
      if (!data.items.length) {
        renderMessage("No results yet", EMPTY_COPY, false);
        return;
      }
      const frag = document.createDocumentFragment();
      for (const item of data.items) frag.append(renderItem(item));
      galleryEl.replaceChildren(frag);
    } finally {
      galleryEl.setAttribute("aria-busy", "false");
    }
  }

  function setField(name, value) {
    const el = form.elements[name];
    if (!el) return;
    if (el.type === "checkbox") el.checked = value === true || value === 1 || value === "1";
    else if (value === null || value === undefined) el.value = "";
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function applyPresetBundle(params) {
    WS_ADJUST.forEach((key) => {
      const has = Object.prototype.hasOwnProperty.call(params, key);
      setField(key, has ? params[key] : wsDefaults[key]);
    });
    syncSliders();
  }

  async function loadPresets() {
    try {
      const res = await fetch("/api/presets");
      const raw = await res.text();
      let data = null;
      try {
        data = raw ? JSON.parse(raw) : null;
      } catch {
        data = null;
      }
      if (!res.ok || !data) {
        presetHelp.textContent = "Presets unavailable — manual edits still work.";
        return;
      }
      wsDefaults = data.defaults || {};
      wsPresets = data.presets || [];
      wsPresets.forEach((item) => {
        const opt = document.createElement("option");
        opt.value = item.id;
        opt.textContent = item.label || item.id;
        presetSelect.appendChild(opt);
      });
      presetHelp.textContent = CUSTOM_HELP;
    } catch {
      presetHelp.textContent = "Presets unavailable — manual edits still work.";
    }
  }

  async function uploadFiles(fileList) {
    if (uploading || generating) return;
    const files = Array.from(fileList || []).filter(Boolean);
    fileInput.value = "";
    const problem = filesProblem(files);
    if (problem) {
      setStatus(problem, "error");
      return;
    }
    const previousIds = sourceIds.slice();
    const previousId = sourceId;
    uploading = true;
    const busyText = files.length > 1 ? `Uploading ${files.length} images…` : `Uploading “${files[0].name || "image"}”…`;
    setDropTitle(busyText);
    syncControls();
    setStatus(busyText, "progress");
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    try {
      const data = await postForm("/api/upload", body);
      const items = data.items || (data.id ? [data] : []);
      sourceIds = items.map((item) => item.id).filter(Boolean);
      sourceId = sourceIds[0] || null;
      if (!sourceId) throw new Error("Upload succeeded but the server response was incomplete. Try again.");
      const first = items[0];
      preview.src = `${first.url}?t=${Date.now()}`;
      preview.alt = `Source preview, ${first.width} by ${first.height} ${first.format || ""}`.trim();
      previewWrap.classList.remove("hidden");
      const idText = sourceIds.join(", ");
      meta.textContent =
        items.length > 1
          ? `${items.length} images · first ${first.width}×${first.height} · ids ${idText}`
          : `${first.width}×${first.height} · ${first.format} · source ${first.id}`;
      setHint("Ready. Press Generate, or open Advanced to tweak the CPU transform.");
      setStatus(
        items.length > 1
          ? `${items.length} photos uploaded. Press Generate, or open Advanced to tweak the CPU transform.`
          : "Photo uploaded. Press Generate, or open Advanced to tweak the CPU transform.",
        "success",
      );
    } catch (err) {
      sourceIds = previousIds;
      sourceId = previousId;
      setStatus(err.message || "Upload failed.", "error");
    } finally {
      uploading = false;
      fileInput.value = "";
      syncControls();
    }
  }

  function resetForm() {
    if (uploading || generating) return;
    sourceId = null;
    sourceIds = [];
    fileInput.value = "";
    preview.removeAttribute("src");
    preview.alt = "Source preview";
    previewWrap.classList.add("hidden");
    meta.textContent = "";
    form.reset();
    presetSelect.value = "";
    presetHelp.textContent = wsPresets.length ? CUSTOM_HELP : presetHelp.textContent;
    syncSliders();
    clearInvalid();
    setHint("Upload a photo, or paste ids in Advanced, then generate.");
    syncControls();
    setStatus("Form reset.", "success");
    dropzone.focus();
  }

  [bri, con, sat, shp].forEach((input) => input.addEventListener("input", syncSliders));
  ["crop", "max_width", "rotate", "blur_radius", "posterize", "solarize", "colorize_black", "colorize_white", "batch_ids"].forEach(
    (name) => {
      const el = form.elements[name];
      if (el) el.addEventListener("input", () => el.removeAttribute("aria-invalid"));
    },
  );
  batchInput.addEventListener("input", () => {
    if (!uploading && !generating) syncControls();
  });

  presetSelect.addEventListener("change", () => {
    const chosen = wsPresets.find((item) => item.id === presetSelect.value);
    presetHelp.textContent = chosen ? chosen.description : CUSTOM_HELP;
    applyPresetBundle(chosen ? chosen.params : {});
  });

  dropzone.addEventListener("click", () => {
    if (uploading || generating) return;
    fileInput.click();
  });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      dropzone.classList.remove("drag");
      return;
    }
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    if (uploading || generating) return;
    fileInput.click();
  });
  ["dragenter", "dragover"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      if (uploading || generating) return;
      dropzone.classList.add("drag");
    });
  });
  ["dragleave", "drop"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("drag");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const files = event.dataTransfer ? event.dataTransfer.files : null;
    if (!files || !files.length || uploading || generating) return;
    uploadFiles(files);
  });
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => event.preventDefault());
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length) uploadFiles(fileInput.files);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (uploading || generating) return;
    const problem = validateForm();
    if (problem) {
      if (problem.field) {
        problem.field.setAttribute("aria-invalid", "true");
        revealField(problem.field);
      }
      setStatus(problem.message, "error");
      return;
    }
    const ids = batchIds();
    const body = new FormData();
    body.append("source_ids", ids.join(","));
    body.append("source_id", ids[0]);
    body.append("preset", form.elements.preset.value);
    body.append("crop", form.elements.crop.value.trim());
    body.append("max_width", String(form.elements.max_width.value || "0").trim() || "0");
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
    const consentEl = form.elements.consent_attested;
    body.append("consent_attested", consentEl && consentEl.checked ? "true" : "false");
    generating = true;
    syncControls();
    setStatus(ids.length > 1 ? `Generating ${ids.length} images on CPU…` : "Generating on CPU…", "progress");
    try {
      const data = await postForm("/api/generate", body);
      const count = data.count || (data.items ? data.items.length : 1);
      const failed = Array.isArray(data.errors) ? data.errors : [];
      if (!data.after && !(data.items && data.items.length)) {
        throw new Error("Generate finished but no result image was returned.");
      }
      if (failed.length) {
        const why = failed
          .map((item) => (item && item.detail ? `${item.id ? item.id + ": " : ""}${item.detail}` : "One image failed."))
          .join(" ");
        setStatus(`Saved ${count} result${count === 1 ? "" : "s"}. ${failed.length} failed. ${why}`, "error");
      } else {
        setStatus(
          count > 1
            ? `Added ${count} results to the gallery. Outputs labelled AI-assisted / transformed (CPU).`
            : "Added to the gallery. Output labelled AI-assisted / transformed (CPU).",
          "success",
        );
      }
      await loadGallery();
      const first = galleryEl.querySelector(".pair");
      if (first) first.scrollIntoView({ block: "nearest" });
    } catch (err) {
      setStatus(err.message || "Generate failed.", "error");
    } finally {
      generating = false;
      syncControls();
    }
  });

  resetBtn.addEventListener("click", resetForm);
  syncSliders();
  syncControls();
  loadPresets();
  loadGallery();
})();

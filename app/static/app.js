"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  lines: [],
  width: 1,
  height: 1,
  selectedId: null,
  mode: "select",
  scale: 1,
  calibrated: false,
  history: [],
  future: [],
  drag: null,
  draftStart: null,
};

const elements = {
  upload: $("#upload-screen"), loading: $("#loading-screen"), editor: $("#editor-screen"),
  fileInput: $("#file-input"), dropzone: $("#dropzone"), drawing: $("#drawing"),
  sketch: $("#sketch-image"), lineLayer: $("#line-layer"), handleLayer: $("#handle-layer"),
  draft: $("#draft-line"), toast: $("#toast"), hint: $("#canvas-hint"),
};

function snapshot() { return JSON.stringify(state.lines); }
function checkpoint() {
  state.history.push(snapshot());
  if (state.history.length > 50) state.history.shift();
  state.future = [];
}
function restore(value) {
  state.lines = JSON.parse(value);
  if (!state.lines.some((line) => line.id === state.selectedId)) state.selectedId = null;
  render();
}
function undo() {
  if (!state.history.length) return;
  state.future.push(snapshot());
  restore(state.history.pop());
}
function redo() {
  if (!state.future.length) return;
  state.history.push(snapshot());
  restore(state.future.pop());
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { elements.toast.hidden = true; }, 4200);
}

function showScreen(name) {
  elements.upload.hidden = name !== "upload";
  elements.loading.hidden = name !== "loading";
  elements.editor.hidden = name !== "editor";
}

async function processFile(file) {
  if (!file) return;
  if (!["image/jpeg", "image/png"].includes(file.type)) return showToast("Выберите JPEG или PNG", true);
  if (file.size > 20 * 1024 * 1024) return showToast("Файл больше 20 МБ", true);
  showScreen("loading");
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch("/api/v1/detect", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Не удалось обработать изображение");
    state.lines = result.lines.map((line, index) => ({ ...line, id: line.id || `line-${Date.now()}-${index}` }));
    state.width = result.image_width_px;
    state.height = result.image_height_px;
    state.selectedId = null;
    state.history = [];
    state.future = [];
    state.scale = 1;
    state.calibrated = false;
    elements.drawing.setAttribute("viewBox", `0 0 ${state.width} ${state.height}`);
    elements.sketch.setAttribute("width", state.width);
    elements.sketch.setAttribute("height", state.height);
    elements.sketch.setAttribute("href", result.preview_image || URL.createObjectURL(file));
    $("#file-name").textContent = file.name;
    $("#scale-result b").textContent = "1 мм / пиксель";
    showScreen("editor");
    render();
    showToast(`${state.lines.length} линий найдено${result.perspective_corrected ? ", перспектива исправлена" : ""}`);
  } catch (error) {
    showScreen("upload");
    showToast(error.message, true);
  }
}

function selectedLine() { return state.lines.find((line) => line.id === state.selectedId); }
function length(line) { return Math.hypot(line.end.x - line.start.x, line.end.y - line.start.y); }
function svgPoint(event) {
  const point = elements.drawing.createSVGPoint();
  point.x = event.clientX; point.y = event.clientY;
  const result = point.matrixTransform(elements.drawing.getScreenCTM().inverse());
  return { x: Math.max(0, Math.min(state.width, result.x)), y: Math.max(0, Math.min(state.height, result.y)) };
}
function snapPoint(start, end, event) {
  if (!event.shiftKey) return end;
  const dx = Math.abs(end.x - start.x), dy = Math.abs(end.y - start.y);
  return dx > dy ? { x: end.x, y: start.y } : { x: start.x, y: end.y };
}

function lineElement(line) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "line");
  for (const [name, value] of Object.entries({ x1: line.start.x, y1: line.start.y, x2: line.end.x, y2: line.end.y })) node.setAttribute(name, value);
  node.setAttribute("class", `drawing-line ${line.kind || "wall"} ${line.reviewed ? "" : "unreviewed"} ${line.id === state.selectedId ? "selected" : ""}`);
  node.dataset.id = line.id;
  node.addEventListener("pointerdown", (event) => {
    if (state.mode !== "select") return;
    event.stopPropagation();
    state.selectedId = line.id;
    render();
  });
  return node;
}

function handleElement(line, endpoint) {
  const point = line[endpoint];
  const node = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  node.setAttribute("cx", point.x); node.setAttribute("cy", point.y);
  node.setAttribute("r", Math.max(state.width, state.height) / 135);
  node.setAttribute("class", "handle");
  node.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
    checkpoint();
    state.drag = { id: line.id, endpoint };
    elements.drawing.setPointerCapture(event.pointerId);
  });
  return node;
}

function renderProperties() {
  const line = selectedLine();
  $("#no-selection").hidden = Boolean(line);
  $("#line-properties").hidden = !line;
  $("#selection-badge").textContent = line ? "Выбрана" : "Не выбрана";
  elements.hint.hidden = Boolean(line);
  if (!line) return;
  $("#line-kind").value = line.kind || "wall";
  $("#x1").value = line.start.x.toFixed(1); $("#y1").value = line.start.y.toFixed(1);
  $("#x2").value = line.end.x.toFixed(1); $("#y2").value = line.end.y.toFixed(1);
  $("#pixel-length").textContent = `${length(line).toFixed(1)} px`;
}

function render() {
  elements.lineLayer.replaceChildren(...state.lines.map(lineElement));
  const line = selectedLine();
  elements.handleLayer.replaceChildren(...(line ? [handleElement(line, "start"), handleElement(line, "end")] : []));
  $("#line-count").textContent = state.lines.length;
  $("#undo").disabled = !state.history.length;
  $("#redo").disabled = !state.future.length;
  renderProperties();
}

function setMode(mode) {
  state.mode = mode;
  $$("[data-mode]").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
  elements.drawing.classList.toggle("draw-mode", mode === "draw");
}
function deleteSelected() {
  if (!state.selectedId) return showToast("Сначала выберите линию", true);
  checkpoint();
  state.lines = state.lines.filter((line) => line.id !== state.selectedId);
  state.selectedId = null;
  render();
}

elements.drawing.addEventListener("pointerdown", (event) => {
  if (event.target !== elements.drawing && event.target !== elements.sketch) return;
  if (state.mode === "select") { state.selectedId = null; render(); return; }
  state.draftStart = svgPoint(event);
  elements.draft.hidden = false;
  for (const [key, value] of Object.entries({ x1: state.draftStart.x, y1: state.draftStart.y, x2: state.draftStart.x, y2: state.draftStart.y })) elements.draft.setAttribute(key, value);
  elements.drawing.setPointerCapture(event.pointerId);
});
elements.drawing.addEventListener("pointermove", (event) => {
  if (state.drag) {
    const line = state.lines.find((item) => item.id === state.drag.id);
    if (line) line[state.drag.endpoint] = svgPoint(event);
    render();
    return;
  }
  if (!state.draftStart) return;
  const point = snapPoint(state.draftStart, svgPoint(event), event);
  elements.draft.setAttribute("x2", point.x); elements.draft.setAttribute("y2", point.y);
});
elements.drawing.addEventListener("pointerup", (event) => {
  if (state.drag) { state.drag = null; selectedLine().reviewed = true; render(); return; }
  if (!state.draftStart) return;
  const end = snapPoint(state.draftStart, svgPoint(event), event);
  if (Math.hypot(end.x - state.draftStart.x, end.y - state.draftStart.y) > 4) {
    checkpoint();
    const line = { id: `manual-${Date.now()}`, start: state.draftStart, end, confidence: 1, source: "manual", kind: "wall", reviewed: true };
    state.lines.push(line); state.selectedId = line.id;
  }
  state.draftStart = null; elements.draft.hidden = true; render();
});
elements.drawing.addEventListener("pointercancel", () => { state.drag = null; state.draftStart = null; elements.draft.hidden = true; render(); });

$$('[data-mode]').forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
$("#delete-line").addEventListener("click", deleteSelected);
$("#undo").addEventListener("click", undo); $("#redo").addEventListener("click", redo);
$("#new-file").addEventListener("click", () => { elements.fileInput.value = ""; showScreen("upload"); });
$("#opacity").addEventListener("input", (event) => { elements.sketch.style.opacity = Number(event.target.value) / 100; });

for (const [id, path] of [["x1", ["start", "x"]], ["y1", ["start", "y"]], ["x2", ["end", "x"]], ["y2", ["end", "y"]]]) {
  $("#" + id).addEventListener("change", (event) => {
    const line = selectedLine(); if (!line || !Number.isFinite(Number(event.target.value))) return;
    checkpoint(); line[path[0]][path[1]] = Number(event.target.value); line.reviewed = true; render();
  });
}
$("#line-kind").addEventListener("change", (event) => {
  const line = selectedLine(); if (!line) return;
  checkpoint(); line.kind = event.target.value; line.reviewed = true; render();
});
$("#calibrate").addEventListener("click", () => {
  const line = selectedLine(); const millimeters = Number($("#known-length").value);
  if (!line) return showToast("Выберите линию с известной длиной", true);
  if (!Number.isFinite(millimeters) || millimeters <= 0) return showToast("Введите реальную длину в миллиметрах", true);
  state.scale = millimeters / length(line); state.calibrated = true;
  $("#scale-result b").textContent = `${state.scale.toFixed(4)} мм / пиксель`;
  showToast("Масштаб рассчитан");
});

$("#export-button").addEventListener("click", async () => {
  if (!state.lines.length) return showToast("На чертеже нет линий", true);
  if (!state.calibrated && !confirm("Масштаб не откалиброван. Скачать DXF в масштабе 1 мм на пиксель?")) return;
  const filename = ($("#file-name").textContent.replace(/\.[^.]+$/, "") || "drawing") + ".dxf";
  try {
    const response = await fetch("/api/v1/export/dxf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: state.lines, units: "mm", scale_mm_per_pixel: state.scale, filename }),
    });
    if (!response.ok) { const detail = await response.json(); throw new Error(detail.detail || "Ошибка экспорта"); }
    const blob = await response.blob(); const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href);
    showToast("DXF готов и скачан");
  } catch (error) { showToast(error.message, true); }
});

elements.fileInput.addEventListener("change", (event) => processFile(event.target.files[0]));
for (const name of ["dragenter", "dragover"]) elements.dropzone.addEventListener(name, (event) => { event.preventDefault(); elements.dropzone.classList.add("drag"); });
for (const name of ["dragleave", "drop"]) elements.dropzone.addEventListener(name, (event) => { event.preventDefault(); elements.dropzone.classList.remove("drag"); });
elements.dropzone.addEventListener("drop", (event) => processFile(event.dataTransfer.files[0]));
document.addEventListener("keydown", (event) => {
  if (["INPUT", "SELECT"].includes(document.activeElement.tagName)) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); }
  else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
  else if (event.key === "Delete" || event.key === "Backspace") deleteSelected();
  else if (event.key.toLowerCase() === "v") setMode("select");
  else if (event.key.toLowerCase() === "l") setMode("draw");
  else if (event.key === "Escape") { state.selectedId = null; setMode("select"); render(); }
});

fetch("/health").catch(() => { $("#service-status").innerHTML = "<i></i> Сервис недоступен"; });

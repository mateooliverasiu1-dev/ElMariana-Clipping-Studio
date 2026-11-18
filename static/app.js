/* ElMariana Clipping Studio — interfaz (JavaScript sin dependencias). */
"use strict";

const S = {
  health: null,
  projects: [],
  project: null,
  clipId: null,
  clipDetail: null,   // respuesta de GET clip (incluye subtitle_words)
  words: [],          // copia editable de los subtítulos
  player: "original",
  pollTimer: null,
  lastClipSig: "",
};

/* ------------------------------------------------------------ utilidades */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    let msg = typeof d === "string" ? d : d && d.message ? d.message : `Error ${res.status}`;
    if (d && d.required_actions) msg += "\n• " + d.required_actions.join("\n• ");
    if (Array.isArray(d)) msg = d.map((e) => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`).join("\n");
    throw new Error(msg);
  }
  return data;
}

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v; // solo para contenido estático propio
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const $ = (sel) => document.querySelector(sel);
const fmt = (s) => {
  s = Math.max(0, Number(s) || 0);
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`;
};
const bytes = (n) => (n > 1e9 ? (n / 1e9).toFixed(2) + " GB" : (n / 1e6).toFixed(1) + " MB");

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (bad ? " bad" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), bad ? 7000 : 3500);
}

function chip(text, kind = "") {
  return h("span", { class: "chip " + kind }, text);
}

const STATUS = {
  uploaded: ["Subido", "info"], queued: ["En cola", "info"], processing: ["Procesando", "info"],
  ready: ["Listo", "ok"], error: ["Error", "bad"], blocked: ["Bloqueado", "bad"],
};
const CLIP_STATUS = {
  candidate: ["Candidato", ""], edited: ["Editado (re-exportar)", "warn"], queued: ["En cola", "info"],
  rendering: ["Exportando", "info"], exported: ["Exportado ✓", "ok"], qc_failed: ["QC no pasó", "bad"],
  error: ["Error", "bad"],
};
const RIGHTS = { APPROVED: "ok", "REVIEW REQUIRED": "warn", BLOCKED: "bad" };

/* ------------------------------------------------------------ salud */
async function loadHealth() {
  try {
    S.health = await api("/api/health");
  } catch (e) {
    S.health = null;
  }
  const box = $("#health");
  box.replaceChildren();
  if (!S.health) return box.append(chip("API sin conexión", "bad"));
  box.append(
    chip(S.health.ffmpeg ? "FFmpeg ✓" : "FFmpeg no encontrado", S.health.ffmpeg ? "ok" : "bad"),
    chip(S.health.faster_whisper ? `Whisper ✓ (${S.health.whisper_default_model})` : "Faster-Whisper no instalado",
      S.health.faster_whisper ? "ok" : "bad"),
    S.health.face_detection === "ok" ? chip("Caras ✓", "ok")
      : chip(`Detección de caras: ${S.health.face_detection} (encuadre centrado)`, "warn"),
    chip("v" + S.health.version),
  );
  fillRightsFieldsets();
}

/* ------------------------------------------------------------ proyectos */
async function loadProjects() {
  S.projects = await api("/api/projects");
  renderProjectList();
}

function renderProjectList() {
  const list = $("#projectList");
  list.replaceChildren();
  if (!S.projects.length) return list.append(h("p", { class: "muted small" }, "Sin proyectos todavía."));
  for (const p of S.projects) {
    const [label, kind] = STATUS[p.status] || [p.status, ""];
    const pct = p.progress ? p.progress.percent : 0;
    list.append(h("div", {
      class: "project-item" + (S.project && S.project.id === p.id ? " active" : ""),
      onclick: () => openProject(p.id),
    },
      h("div", { class: "name", title: p.name }, p.name),
      ["processing", "queued"].includes(p.status) ? h("div", { class: "bar", style: "margin-top:8px" }, h("i", { style: `width:${pct}%` })) : null,
      h("div", { class: "meta" }, chip(label, kind),
        h("span", { class: "muted small" }, `${p.clip_count} clips · ${p.exported} ✓`)),
    ));
  }
}

function showDashboard() {
  S.project = null;
  S.clipId = null;
  renderProjectList();
  const totalClips = S.projects.reduce((a, p) => a + p.clip_count, 0);
  const exported = S.projects.reduce((a, p) => a + p.exported, 0);
  const drop = h("label", { class: "dropzone big-drop", onclick: (e) => { e.preventDefault(); openUpload(); } },
    h("span", { class: "dz-icon" }, "⬆"),
    h("strong", {}, "Sube un video autorizado"),
    h("span", {}, "MP4, MOV o MKV · se transcribe, se buscan los mejores momentos y se proponen Shorts"));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    if (e.dataTransfer.files[0]) openUpload(e.dataTransfer.files[0]);
  });
  $("#main").replaceChildren(
    h("h1", { style: "margin-bottom:6px" }, "Panel principal"),
    h("p", { class: "muted", style: "margin:0 0 20px" }, "Convierte videos con derechos de uso en candidatos para YouTube Shorts."),
    h("div", { class: "hero" },
      h("div", { class: "card" }, drop),
      h("div", { class: "card" },
        h("h3", {}, "Flujo de trabajo"),
        h("ol", { class: "steps" },
          h("li", {}, "Sube el video y documenta el permiso de uso."),
          h("li", {}, "Análisis con FFmpeg + transcripción con Faster-Whisper."),
          h("li", {}, "Detección de momentos: diálogo, reacciones, audio y escenas."),
          h("li", {}, "Revisa los candidatos, ajusta tiempos y subtítulos."),
          h("li", {}, "Exporta en 9:16 con subtítulos dinámicos y zooms suaves."),
          h("li", {}, "Control de calidad + derechos → descarga y publica tú (aprobación humana)."),
        ),
      ),
    ),
    h("div", { class: "stats" },
      h("div", { class: "card stat" }, h("b", {}, S.projects.length), h("span", {}, "proyectos")),
      h("div", { class: "card stat" }, h("b", {}, totalClips), h("span", {}, "clips detectados")),
      h("div", { class: "card stat" }, h("b", {}, exported), h("span", {}, "Shorts exportados con QC ✓")),
    ),
  );
}

async function openProject(pid, keepClip = false) {
  try {
    S.project = await api(`/api/projects/${pid}`);
  } catch (e) {
    toast(e.message, true);
    return loadProjects().then(showDashboard);
  }
  if (!keepClip) {
    S.clipId = S.project.clips.length ? S.project.clips[0].id : null;
    S.lastClipSig = "";
  }
  renderProjectList();
  renderProject();
  if (S.clipId) await selectClip(S.clipId, true);
  schedulePoll();
}

function renderProject() {
  const p = S.project;
  const m = p.media || {};
  const rv = p.rights_review;
  const [label, kind] = STATUS[p.status] || [p.status, ""];

  const head = h("div", { class: "project-head" },
    h("div", {},
      h("h1", {}, p.name),
      h("div", { class: "info" },
        chip(label, kind),
        chip(`Derechos: ${rv.status}`, RIGHTS[rv.status]),
        chip(`${fmt(m.duration)} · ${m.width}x${m.height} · ${m.fps} fps`),
        chip(`${m.video_codec}/${m.audio_codec || "sin audio"}`),
        chip(bytes(m.size_bytes || 0)),
        p.language_detected ? chip(`Idioma: ${p.language_detected}`) : null,
        p.transcript_stats ? chip(`${p.transcript_stats.words} palabras · Whisper ${p.transcript_stats.model}`) : null,
      ),
    ),
    h("div", { class: "actions", style: "margin:0" },
      h("button", { class: "btn", onclick: openRights }, "Derechos"),
      h("button", { class: "btn", onclick: reprocess, disabled: p.processing || null }, "Re-analizar"),
      h("button", { class: "btn danger", onclick: deleteProject, disabled: p.processing || null }, "Eliminar"),
    ),
  );

  const parts = [head];
  if (rv.status !== "APPROVED") {
    parts.push(h("div", { class: "card", style: "margin-bottom:18px;border-color:#5c4a14" },
      h("h3", { class: "lvl-warning" }, `Derechos: ${rv.status} — la exportación final está bloqueada`),
      h("ul", { class: "reasons" }, [...rv.risks, ...rv.required_actions].map((r) => h("li", {}, r))),
    ));
  }
  if (["queued", "processing", "error", "blocked"].includes(p.status)) {
    const pr = p.progress || {};
    parts.push(h("div", { class: "card progress-card", id: "progressCard" },
      h("div", { class: "row" }, h("strong", {}, pr.message || pr.stage), h("span", { class: "muted" }, `${pr.percent || 0}%`)),
      h("div", { class: "bar" }, h("i", { style: `width:${pr.percent || 0}%` })),
    ));
  }

  if (p.status === "ready" && !p.clips.length) {
    parts.push(h("div", { class: "card empty" }, p.progress.message || "No se encontraron clips."));
  } else if (p.clips.length) {
    parts.push(h("div", { class: "workspace" },
      h("div", {}, h("h3", { style: "margin-bottom:10px" }, `Clips detectados (${p.clips.length})`),
        h("div", { class: "clip-list", id: "clipList" })),
      h("div", { class: "detail", id: "clipDetail" }),
    ));
  }
  $("#main").replaceChildren(...parts);
  renderClipList();
}

function scoreClass(s) { return s >= 70 ? "hi" : s >= 45 ? "mid" : "lo"; }

function renderClipList() {
  const list = $("#clipList");
  if (!list) return;
  list.replaceChildren();
  for (const c of S.project.clips) {
    const [label, kind] = CLIP_STATUS[c.status] || [c.status, ""];
    list.append(h("div", { class: "clip-card" + (c.id === S.clipId ? " active" : ""), onclick: () => selectClip(c.id) },
      c.thumbnail ? h("img", { src: `/api/projects/${S.project.id}/clips/${c.id}/thumbnail`, alt: "" }) : h("div", { class: "noimg" }),
      h("div", {},
        h("div", { class: "t" }, c.title),
        h("div", { class: "m" },
          h("span", { class: "score " + scoreClass(c.score) }, c.score),
          h("span", { class: "muted small" }, `${fmt(c.start)}–${fmt(c.end)} · ${c.duration.toFixed(0)} s`),
          chip(label + (c.status === "rendering" ? ` ${c.render_progress || 0}%` : ""), kind),
        ),
      ),
    ));
  }
}

async function selectClip(cid, force = false) {
  if (!force && cid === S.clipId && S.clipDetail) return;
  S.clipId = cid;
  S.player = "original";
  renderClipList();
  try {
    S.clipDetail = await api(`/api/projects/${S.project.id}/clips/${cid}`);
  } catch (e) {
    return toast(e.message, true);
  }
  S.words = S.clipDetail.subtitle_words.map((w) => ({ ...w }));
  const c = currentClip();
  if (c && c.render && ["exported", "qc_failed"].includes(c.status)) S.player = "edited";
  renderClipDetail();
}

const currentClip = () => S.project && S.project.clips.find((c) => c.id === S.clipId);
const clipSig = (c) => c ? `${c.status}|${c.render_progress}|${c.rendered_at}|${c.error}` : "";

/* ------------------------------------------------------------ detalle del clip */
function renderClipDetail() {
  const box = $("#clipDetail");
  const c = currentClip();
  if (!box || !c) return;
  S.lastClipSig = clipSig(c);
  box.replaceChildren(
    previewSection(c),
    timingSection(c),
    exportSection(c),
    subtitleSection(),
    h("div", { class: "cols2" }, seoSection(c), analysisSection(c)),
  );
}

function previewSection(c) {
  const pid = S.project.id;
  const edited = S.player === "edited" && c.render;
  const video = h("video", { id: "player", controls: true, preload: "metadata", playsinline: true });
  video.src = edited ? `/api/projects/${pid}/clips/${c.id}/output?v=${c.rendered_at || 0}` : `/api/projects/${pid}/media`;
  if (!edited) {
    video.addEventListener("loadedmetadata", () => { video.currentTime = c.start; });
    video.addEventListener("timeupdate", () => {
      if (video.currentTime >= c.end) { video.pause(); video.currentTime = c.start; }
      highlightCurrentWord(video.currentTime);
    });
    video.addEventListener("play", () => {
      if (video.currentTime < c.start - 0.5 || video.currentTime >= c.end) video.currentTime = c.start;
    });
  }
  const tabs = h("div", { class: "player-tabs" },
    h("button", { class: "btn sm" + (!edited ? " on" : ""), onclick: () => { S.player = "original"; renderClipDetail(); } }, "Fragmento original"),
    h("button", {
      class: "btn sm" + (edited ? " on" : ""), disabled: !c.render || null,
      onclick: () => { S.player = "edited"; renderClipDetail(); },
    }, "Short editado 9:16"),
  );
  const info = h("div", { class: "card" },
    h("h3", {}, "Clip seleccionado"),
    h("dl", { class: "kv" },
      h("dt", {}, "Puntuación"), h("dd", {}, h("span", { class: "score " + scoreClass(c.score) }, c.score), " / 100"),
      h("dt", {}, "Inicio"), h("dd", {}, fmt(c.start)),
      h("dt", {}, "Final"), h("dd", {}, fmt(c.end)),
      h("dt", {}, "Duración"), h("dd", {}, `${c.duration.toFixed(1)} s`),
      h("dt", {}, "Estilo"), h("dd", {}, c.edit_style),
    ),
    c.context_note ? h("p", { class: "lvl-warning small" }, "⚠ " + c.context_note) : null,
  );
  return h("div", {},
    tabs,
    h("div", { class: "preview-grid" },
      h("div", { class: "player-wrap" + (edited ? " vertical" : "") }, video),
      info),
  );
}

function timingSection(c) {
  const startIn = h("input", { type: "number", step: "0.1", min: "0", value: c.start });
  const endIn = h("input", { type: "number", step: "0.1", min: "0", value: c.end });
  const titleIn = h("input", { value: c.title, maxlength: "100" });
  const cur = () => { const v = $("#player"); return v && S.player === "original" ? v.currentTime.toFixed(2) : null; };
  return h("div", { class: "card" },
    h("h3", {}, "Tiempos y título"),
    h("label", {}, "Título del clip", titleIn),
    h("div", { class: "time-row", style: "margin-top:10px" },
      h("label", {}, "Inicio (s)", startIn),
      h("label", {}, "Final (s)", endIn),
      h("button", { class: "btn sm", type: "button", onclick: () => { const t = cur(); if (t) startIn.value = t; } }, "Inicio = posición"),
      h("button", { class: "btn sm", type: "button", onclick: () => { const t = cur(); if (t) endIn.value = t; } }, "Final = posición"),
    ),
    h("div", { class: "actions" },
      h("button", {
        class: "btn primary sm", onclick: () => saveClip({
          title: titleIn.value, start: parseFloat(startIn.value), end: parseFloat(endIn.value),
        }, true),
      }, "Guardar cambios"),
    ),
  );
}

function exportSection(c) {
  const pid = S.project.id;
  const rv = S.project.rights_review;
  const opts = (c.render && c.render.options) || { layout: "auto", zoom: "suave", subtitles: true, remove_pauses: true };
  const sel = (name, options, value) => h("select", { name },
    ...options.map(([v, l]) => h("option", { value: v, selected: v === value || null }, l)));
  const layout = sel("layout", [["auto", "Automático"], ["crop", "Recorte al hablante"], ["fit", "Completo + fondo desenfocado"]], opts.layout);
  const zoom = sel("zoom", [["suave", "Suave"], ["normal", "Normal"], ["off", "Sin zoom"]], opts.zoom);
  const subs = sel("subtitles", [["1", "Sí"], ["0", "No"]], opts.subtitles ? "1" : "0");
  const pauses = sel("remove_pauses", [["1", "Sí"], ["0", "No"]], opts.remove_pauses ? "1" : "0");
  const busy = ["queued", "rendering"].includes(c.status);
  const parts = [
    h("h3", {}, "Edición automática y exportación"),
    h("div", { class: "options-row" },
      h("label", {}, "Encuadre 9:16", layout),
      h("label", {}, "Zooms", zoom),
      h("label", {}, "Subtítulos", subs),
      h("label", {}, "Cortar pausas", pauses),
    ),
    h("div", { class: "actions" },
      h("button", {
        class: "btn primary", disabled: busy || rv.status === "BLOCKED" || null,
        onclick: () => renderClip({
          layout: layout.value, zoom: zoom.value, subtitles: subs.value === "1", remove_pauses: pauses.value === "1",
        }),
      }, busy ? "Exportando…" : c.render ? "Volver a exportar" : "Exportar Short"),
    ),
  ];
  if (busy) {
    parts.push(h("div", { style: "margin-top:12px" },
      h("div", { class: "row muted small" }, c.status === "queued" ? "En cola…" : `Renderizando… ${c.render_progress || 0}%`),
      h("div", { class: "bar" }, h("i", { style: `width:${c.render_progress || 0}%` }))));
  }
  if (c.status === "error" && c.error) parts.push(h("p", { class: "error-box", style: "margin-top:12px" }, c.error));
  if (c.render && c.qc && !busy) {
    const qc = c.qc;
    const r = c.render;
    const canDownload = qc.status === "PASS" && rv.status === "APPROVED" && c.status === "exported";
    parts.push(
      h("div", { class: "actions", style: "align-items:center" },
        chip(`Control de calidad: ${qc.status}`, qc.status === "PASS" ? "ok" : "bad"),
        chip(`Derechos: ${rv.status}`, RIGHTS[rv.status]),
        chip(`${r.duration}s · ${r.cuts} cortes · ${r.zooms.length} zooms · ${r.layout}`),
        c.status === "edited" ? chip("Cambios sin exportar", "warn") : null,
      ),
      h("div", { class: "actions" },
        h("a", { class: "btn primary" + (canDownload ? "" : " hidden"), href: `/api/projects/${pid}/clips/${c.id}/download` }, "⬇ Descargar MP4"),
        r.srt ? h("a", { class: "btn" + (canDownload ? "" : " hidden"), href: `/api/projects/${pid}/clips/${c.id}/download?kind=srt` }, "Subtítulos .srt") : null,
        h("a", { class: "btn" + (canDownload ? "" : " hidden"), href: `/api/projects/${pid}/clips/${c.id}/download?kind=metadata` }, "Título y descripción .txt"),
        !canDownload ? h("span", { class: "muted small" }, "La descarga se habilita con QC PASS y derechos APPROVED.") : null,
      ),
      qcReport(qc, r),
    );
  }
  return h("div", { class: "card" }, ...parts);
}

function qcReport(qc, r) {
  const items = [];
  for (const p of qc.problems) {
    items.push(h("li", {}, h("span", { class: "lvl-" + p.level }, p.level === "error" ? "✕ " : "⚠ "),
      `[${p.area}] ${p.message}`, p.fix ? h("div", { class: "fix" }, "→ " + p.fix) : null));
  }
  for (const t of [...qc.technical_report, ...qc.editorial_report]) items.push(h("li", {}, h("span", { class: "lvl-ok" }, "✓ "), t));
  for (const t of qc.manual_checks) items.push(h("li", { class: "muted" }, "☐ Revisión manual: " + t));
  return h("details", { style: "margin-top:12px", open: qc.status !== "PASS" || null },
    h("summary", {}, "Informe de calidad y edición"),
    h("ul", { class: "qc-list" }, items),
    h("p", { class: "muted small" },
      `Zooms: ${r.zooms.map((z) => `${z.start}s`).join(", ") || "ninguno"} · Pausas recortadas: ${r.removed_seconds}s · `
      + `Exportación: ${r.export_settings.resolution}, ${r.export_settings.video}, ${r.export_settings.audio}`),
  );
}

/* ------------------------------------------------------------ editor de subtítulos */
function subtitleSection() {
  const ed = h("div", { class: "sub-editor", id: "subEditor" });
  S.words.forEach((w, i) => {
    const input = h("input", { value: w.w, size: Math.max(2, w.w.length), title: `${fmt(w.start)} – ${fmt(w.end)}` });
    input.addEventListener("input", () => { w.w = input.value; input.size = Math.max(2, input.value.length); });
    input.addEventListener("focus", () => {
      const v = $("#player");
      if (v && S.player === "original") v.currentTime = w.start;
    });
    const star = h("button", { type: "button", title: "Resaltar: automático → sí → no" }, w.hl === true ? "★" : w.hl === false ? "✕" : "☆");
    const el = h("span", {
      class: "word" + (w.hl ? " hl" : "") + (w.p !== undefined && w.p !== null && w.p < 0.5 ? " lowconf" : ""),
      "data-i": i,
    }, input, star);
    star.addEventListener("click", () => {
      w.hl = w.hl === null || w.hl === undefined ? true : w.hl === true ? false : null;
      star.textContent = w.hl === true ? "★" : w.hl === false ? "✕" : "☆";
      el.classList.toggle("hl", w.hl === true);
    });
    ed.append(el);
  });
  return h("div", { class: "card" },
    h("h3", {}, "Editor de subtítulos"),
    h("p", { class: "muted small", style: "margin:-6px 0 10px" },
      "Corrige el texto palabra por palabra (vacía una palabra para quitarla). ★ = resaltar, ✕ = no resaltar, ☆ = automático. "
      + "Subrayado amarillo: baja confianza de transcripción."),
    S.words.length ? ed : h("p", { class: "muted" }, "Este clip no tiene palabras transcritas."),
    h("div", { class: "actions" },
      h("button", { class: "btn primary sm", onclick: saveWords, disabled: !S.words.length || null }, "Guardar subtítulos"),
      h("button", { class: "btn sm", onclick: () => saveClip({ reset_words: true }, true) }, "Restaurar transcripción"),
    ),
  );
}

function highlightCurrentWord(t) {
  const ed = $("#subEditor");
  if (!ed) return;
  const i = S.words.findIndex((w) => t >= w.start && t < w.end + 0.05);
  ed.querySelectorAll(".word.now").forEach((n) => n.classList.remove("now"));
  if (i >= 0) {
    const el = ed.querySelector(`[data-i="${i}"]`);
    if (el) el.classList.add("now");
  }
}

async function saveWords() {
  const words = S.words.map((w) => ({ w: w.w.trim(), start: w.start, end: w.end, hl: w.hl ?? null, p: w.p ?? null }))
    .filter((w) => w.w);
  await saveClip({ words }, true);
}

/* ------------------------------------------------------------ SEO y análisis */
function seoSection(c) {
  const seo = c.seo || { titles: [], hashtags: [] };
  const titleInputs = (seo.titles.length ? seo.titles : [c.title]).map((t) => h("input", { value: t }));
  const desc = h("textarea", { rows: "5" }, seo.description || "");
  const tags = h("input", { value: (seo.hashtags || []).join(" ") });
  const pinned = h("input", { value: seo.pinned_comment || "" });
  return h("div", { class: "card" },
    h("h3", {}, "Título, descripción y hashtags"),
    h("label", { class: "seo-titles" }, "Opciones de título (usa ⇧ para elegir)",
      ...titleInputs.map((inp) => h("div", { style: "display:flex;gap:6px;align-items:center" }, inp,
        h("button", { class: "btn sm", type: "button", title: "Usar como título", onclick: () => saveClip({ title: inp.value }, false) }, "⇧")))),
    h("label", {}, "Descripción", desc),
    h("label", { style: "margin-top:8px" }, "Hashtags", tags),
    h("label", { style: "margin-top:8px" }, "Comentario fijado sugerido", pinned),
    h("p", { class: "muted small" }, `Generado con ${seo.generator || "reglas locales"} a partir de frases reales del clip. Revísalo antes de publicar.`),
    h("div", { class: "actions" },
      h("button", {
        class: "btn primary sm", onclick: () => saveClip({
          seo: {
            titles: titleInputs.map((i) => i.value).filter(Boolean), description: desc.value,
            hashtags: tags.value.split(/\s+/).filter(Boolean).map((t) => (t.startsWith("#") ? t : "#" + t)),
            pinned_comment: pinned.value,
          },
        }, false),
      }, "Guardar metadatos")),
  );
}

const FEAT_LABELS = {
  energy: "Audio", reactions: "Reacciones", hook: "Gancho", payoff: "Remate",
  density: "Ritmo", context: "Contexto", scenes: "Escenas", liveliness: "Sin silencios",
};

function analysisSection(c) {
  return h("div", { class: "card" },
    h("h3", {}, "Por qué se eligió"),
    h("ul", { class: "reasons" }, c.reasons.map((r) => h("li", {}, r))),
    h("div", { style: "margin-top:12px" }, Object.entries(c.features || {}).map(([k, v]) =>
      h("div", { class: "feat" }, h("span", {}, FEAT_LABELS[k] || k),
        h("div", { class: "bar" }, h("i", { style: `width:${Math.round(v * 100)}%` })),
        h("span", {}, Math.round(v * 100))))),
    h("details", { style: "margin-top:10px" }, h("summary", {}, "Transcripción del fragmento"),
      h("p", { class: "muted" }, c.text)),
  );
}

/* ------------------------------------------------------------ acciones */
async function saveClip(body, reloadWords) {
  try {
    await api(`/api/projects/${S.project.id}/clips/${S.clipId}`, { method: "PUT", body: JSON.stringify(body) });
    toast("Cambios guardados");
    S.project = await api(`/api/projects/${S.project.id}`);
    renderClipList();
    if (reloadWords) await selectClip(S.clipId, true);
    else renderClipDetail();
  } catch (e) {
    toast(e.message, true);
  }
}

async function renderClip(options) {
  try {
    await api(`/api/projects/${S.project.id}/clips/${S.clipId}/render`, { method: "POST", body: JSON.stringify(options) });
    toast("Exportación en cola");
    await refreshProject();
  } catch (e) {
    toast(e.message, true);
  }
}

async function reprocess() {
  if (!confirm("Se volverán a detectar los clips y se perderán las ediciones actuales. ¿Continuar?")) return;
  try {
    await api(`/api/projects/${S.project.id}/process`, { method: "POST" });
    await openProject(S.project.id);
  } catch (e) {
    toast(e.message, true);
  }
}

async function deleteProject() {
  if (!confirm(`¿Eliminar el proyecto "${S.project.name}" y todos sus archivos? No se puede deshacer.`)) return;
  try {
    await api(`/api/projects/${S.project.id}`, { method: "DELETE" });
    toast("Proyecto eliminado");
    await loadProjects();
    showDashboard();
  } catch (e) {
    toast(e.message, true);
  }
}

/* ------------------------------------------------------------ sondeo de progreso */
function needsPoll() {
  const p = S.project;
  return p && (p.processing || ["queued", "processing"].includes(p.status)
    || p.clips.some((c) => ["queued", "rendering"].includes(c.status)));
}

function schedulePoll() {
  clearTimeout(S.pollTimer);
  if (needsPoll()) S.pollTimer = setTimeout(refreshProject, 1500);
}

async function refreshProject() {
  if (!S.project) return;
  const prevStatus = S.project.status;
  try {
    S.project = await api(`/api/projects/${S.project.id}`);
  } catch (e) {
    return;
  }
  loadProjects().catch(() => {});
  if (prevStatus !== S.project.status) {
    // terminó (o empezó) el análisis: vista completa
    return openProject(S.project.id);
  }
  if (["queued", "processing", "error", "blocked"].includes(S.project.status)) {
    renderProject();
  } else {
    renderClipList();
    const c = currentClip();
    if (c && clipSig(c) !== S.lastClipSig) {
      if (c.render && ["exported", "qc_failed"].includes(c.status)) S.player = "edited";
      renderClipDetail();
    }
  }
  schedulePoll();
}

/* ------------------------------------------------------------ formularios de derechos */
function fillRightsFieldsets() {
  if (!S.health) return;
  for (const fs of [$("#uploadRights"), $("#editRights")]) {
    fs.replaceChildren($("#rightsFields").content.cloneNode(true));
    const perm = fs.querySelector('[name="permission_type"]');
    for (const [k, v] of Object.entries(S.health.permission_types)) perm.append(h("option", { value: k }, v));
    perm.value = "none";
    for (const name of ["third_party_music", "third_party_footage"]) {
      const s = fs.querySelector(`[name="${name}"]`);
      for (const [k, v] of Object.entries(S.health.third_party_options)) s.append(h("option", { value: k }, v));
      s.value = "unknown";
    }
  }
}

function openRights() {
  const f = $("#rightsForm");
  const d = S.project.rights || {};
  for (const el of f.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = !!d[el.name];
    else if (d[el.name] !== undefined) el.value = d[el.name];
  }
  $("#rightsDialog").showModal();
}

$("#rightsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {};
  for (const el of f.elements) {
    if (!el.name) continue;
    body[el.name] = el.type === "checkbox" ? el.checked : el.value;
  }
  try {
    await api(`/api/projects/${S.project.id}/rights`, { method: "PUT", body: JSON.stringify(body) });
    $("#rightsDialog").close();
    toast("Derechos actualizados");
    await openProject(S.project.id, true);
  } catch (err) {
    toast(err.message, true);
  }
});

/* ------------------------------------------------------------ subida */
let pickedFile = null;

function setPicked(file) {
  pickedFile = file || null;
  $("#dzText").textContent = file ? `${file.name} · ${bytes(file.size)}` : "Arrastra un video MP4, MOV o MKV o haz clic para elegirlo";
}

function openUpload(file) {
  $("#uploadForm").reset();
  fillRightsFieldsets();
  setPicked(file);
  $("#uploadError").classList.add("hidden");
  $("#uploadProgress").classList.add("hidden");
  $("#uploadSubmit").disabled = false;
  $("#uploadDialog").showModal();
}

$("#fileInput").addEventListener("change", (e) => setPicked(e.target.files[0]));
const dz = $("#dropzone");
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => {
  e.preventDefault();
  dz.classList.remove("drag");
  if (e.dataTransfer.files[0]) setPicked(e.dataTransfer.files[0]);
});

function showUploadError(msg) {
  const errBox = $("#uploadError");
  errBox.textContent = msg;
  errBox.classList.remove("hidden");
}

function setUploadProgress(pct, label) {
  const prog = $("#uploadProgress");
  prog.classList.remove("hidden");
  prog.querySelector("i").style.width = pct + "%";
  prog.querySelector("span").textContent = label;
}

/* Sube el archivo en trozos: el túnel de puertos de Codespaces rechaza peticiones grandes (413). */
async function uploadInChunks(file) {
  const init = await api("/api/uploads", { method: "POST", body: JSON.stringify({ filename: file.name, size: file.size }) });
  const uid = init.upload_id;
  let chunk = Math.min(4 * 1024 * 1024, init.max_chunk_bytes);
  let offset = 0;
  let failures = 0;
  const t0 = Date.now();
  while (offset < file.size) {
    const blob = file.slice(offset, offset + chunk);
    let res;
    try {
      res = await fetch(`/api/uploads/${uid}?offset=${offset}`, {
        method: "PUT", body: blob, headers: { "Content-Type": "application/octet-stream" },
      });
    } catch (_) {
      res = null; // error de red: se reintenta
    }
    if (res && res.status === 413 && chunk > 256 * 1024) {
      chunk = Math.floor(chunk / 2); // el túnel aún lo considera grande: trozos más pequeños
      continue;
    }
    if (!res || !res.ok) {
      if (++failures > 5) {
        const d = res ? (await res.json().catch(() => ({}))).detail : null;
        throw new Error(typeof d === "string" ? d : `La subida se interrumpió${res ? ` (error ${res.status})` : ""}. Intenta de nuevo.`);
      }
      await new Promise((r) => setTimeout(r, 1000 * failures));
      continue;
    }
    failures = 0;
    offset = (await res.json()).received;
    const pct = Math.round((offset / file.size) * 100);
    const mbps = offset / 1e6 / Math.max((Date.now() - t0) / 1000, 0.1);
    setUploadProgress(pct, `${pct}% · ${mbps.toFixed(1)} MB/s`);
  }
  return uid;
}

$("#uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  $("#uploadError").classList.add("hidden");
  if (!pickedFile) return showUploadError("Elige un video.");
  const ext = pickedFile.name.split(".").pop().toLowerCase();
  if (!["mp4", "mov", "mkv"].includes(ext)) return showUploadError("Formato no permitido. Usa MP4, MOV o MKV.");

  const fd = new FormData(form);
  fd.delete("file");
  fd.set("confirmed", form.querySelector('[name="confirmed"]').checked ? "true" : "false");
  const rightsBody = {};
  for (const k of ["source_description", "source_url", "rights_holder", "creator_name", "permission_type",
    "evidence", "third_party_music", "third_party_footage", "notes"]) rightsBody[k] = fd.get(k) || "";
  rightsBody.confirmed = fd.get("confirmed") === "true";

  $("#uploadSubmit").disabled = true;
  try {
    // 1) Derechos primero: no se sube nada si están BLOCKED.
    const review = await api("/api/rights/evaluate", { method: "POST", body: JSON.stringify(rightsBody) });
    if (!review.can_process) {
      throw new Error("Derechos BLOCKED: no se puede subir este video.\n• " + review.required_actions.join("\n• "));
    }
    // 2) Video por partes.
    setUploadProgress(0, "0%");
    const uid = await uploadInChunks(pickedFile);
    // 3) Crear el proyecto.
    setUploadProgress(100, "Analizando…");
    fd.set("upload_id", uid);
    const project = await api("/api/projects", { method: "POST", body: fd });
    $("#uploadDialog").close();
    toast("Video subido. Procesando…");
    await loadProjects();
    openProject(project.id);
  } catch (err) {
    showUploadError(err.message);
    $("#uploadProgress").classList.add("hidden");
  } finally {
    $("#uploadSubmit").disabled = false;
  }
});

document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
$("#btnNew").addEventListener("click", () => openUpload());
$("#brand").addEventListener("click", () => { clearTimeout(S.pollTimer); showDashboard(); });

/* ------------------------------------------------------------ inicio */
(async function init() {
  await loadHealth();
  try { await loadProjects(); } catch (e) { toast(e.message, true); }
  showDashboard();
  setInterval(() => { if (!S.project) loadProjects().then(() => { if (!S.project) showDashboard(); }).catch(() => {}); }, 5000);
})();

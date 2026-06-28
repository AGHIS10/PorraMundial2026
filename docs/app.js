const BUILD = document.querySelector('meta[name="app-build"]')?.content || String(Date.now());
const DATA_URL = `./clasificacion.json?v=${BUILD}`;
const PREMIOS_URL = `./premios.json?v=${BUILD}`;
const PARTIDOS_URL = `./partidos.json?v=${BUILD}`;
const RESULTADOS_URL = `./resultados.json?v=${BUILD}`;
const MARCADORES_URL = `./marcadores.json?v=${BUILD}`;
const PARTICIPANTES_URL = `./participantes.json?v=${BUILD}`;
const STATUS_URL = `./status.json?v=${BUILD}`;
const PUNTOS_MAXIMOS = 275;
const SYNC_TIMEZONE = "UTC";
const SYNC_DISPLAY_TIMEZONE = "Europe/Madrid";

const appData = {
  clasificacion: null,
  premios: null,
  partidos: null,
  resultados: null,
  marcadores: null,
  participantes: null,
  evolucion: null,
  status: null,
};

const MEDALS = { 1: "🥇", 2: "🥈", 3: "🥉" };
const PODIUM_ORDER = [2, 1, 3];

const FASE_LABELS = {
  grupos: "Grupos",
  dieciseisavos: "Dieciseisavos",
  octavos: "Octavos",
  cuartos: "Cuartos",
  semifinales: "Semifinales",
  tercer_puesto: "3er puesto",
  final: "Final",
};

/** Fase eliminatoria que muestra la pestaña «Próximos». Cambiar al avanzar el torneo. */
const PROXIMOS_FASE = "dieciseisavos";

const FASE_BADGE_CLASS = {
  grupos: "fase-badge--grupos",
  dieciseisavos: "fase-badge--dieciseisavos",
  octavos: "fase-badge--octavos",
  cuartos: "fase-badge--cuartos",
  semifinales: "fase-badge--semifinales",
  tercer_puesto: "fase-badge--tercer_puesto",
  final: "fase-badge--final",
};

/** Grupos oficiales FIFA A–L (orden fijo para la UI del detalle). */
const GRUPOS_OFICIALES = [
  ["México", "Sudáfrica", "Corea del Sur", "República Checa"],
  ["Canadá", "Bosnia y Herzegovina", "Catar", "Suiza"],
  ["Brasil", "Marruecos", "Haití", "Escocia"],
  ["Estados Unidos", "Paraguay", "Australia", "Turquía"],
  ["Alemania", "Curazao", "Costa de Marfil", "Ecuador"],
  ["Países Bajos", "Japón", "Suecia", "Túnez"],
  ["Bélgica", "Egipto", "Irán", "Nueva Zelanda"],
  ["España", "Cabo Verde", "Arabia Saudí", "Uruguay"],
  ["Francia", "Senegal", "Irak", "Noruega"],
  ["Argentina", "Argelia", "Austria", "Jordania"],
  ["Portugal", "RD Congo", "Uzbekistán", "Colombia"],
  ["Inglaterra", "Croacia", "Ghana", "Panamá"],
];

const elements = {
  loading: document.getElementById("loading"),
  error: document.getElementById("error"),
  errorMessage: document.getElementById("error-message"),
  retryButton: document.getElementById("retry-button"),
  closeErrorButton: document.getElementById("close-error-button"),
  stats: document.getElementById("stats"),
  podiumSection: document.getElementById("podium-section"),
  podium: document.getElementById("podium"),
  premiosSection: document.getElementById("premios-section"),
  premiosList: document.getElementById("premios-list"),
  evolucionSection: document.getElementById("evolucion-section"),
  evolucionPanel: document.getElementById("evolucion-panel"),
  evolucionChart: document.getElementById("evolucion-chart"),
  evolucionRoster: document.getElementById("evolucion-roster"),
  evolucionTooltip: document.getElementById("evolucion-tooltip"),
  iaToggleInput: document.getElementById("ia-toggle-input"),
  leaderboardBody: document.getElementById("leaderboard-body"),
  mobileCards: document.getElementById("mobile-cards"),
  viewHome: document.getElementById("view-home"),
  viewParticipant: document.getElementById("view-participant"),
  btnBack: document.getElementById("btn-back"),
  detailHero: document.getElementById("detail-hero"),
  detailStats: document.getElementById("detail-stats"),
  detailNav: document.getElementById("detail-nav"),
  detailMatches: document.getElementById("detail-matches"),
  predList: document.getElementById("pred-list"),
};

/* ── Data loading ── */

function getMedal(position) {
  return MEDALS[position] || null;
}

function formatPosition(position) {
  const medal = getMedal(position);
  if (medal) {
    return `<span class="medal" aria-label="Posición ${position}">${medal}</span>`;
  }
  return position;
}

function formatPremioPosition(position) {
  const medal = getMedal(position);
  if (medal) return medal;
  return `${position}º`;
}

function formatEuro(amount) {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatSyncDate(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "—";
  const formatted = new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: SYNC_DISPLAY_TIMEZONE,
  }).format(date);
  return formatted.replace(",", " ·");
}

function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "Sin datos de sincronización";

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 0) return "Recién sincronizado";

  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Hace un momento";
  if (minutes < 60) return `Hace ${minutes} minuto${minutes === 1 ? "" : "s"}`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Hace ${hours} hora${hours === 1 ? "" : "s"}`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `Hace ${days} día${days === 1 ? "" : "s"}`;

  const months = Math.floor(days / 30);
  return `Hace ${months} mes${months === 1 ? "" : "es"}`;
}

function formatMatchDateTime(fecha, hora) {
  const [y, m, d] = fecha.split("-");
  return `${d}/${m}/${y} · ${hora}`;
}

function formatMatchDateTimeProminent(fecha, hora) {
  const date = new Date(`${fecha}T${hora}:00`);
  if (Number.isNaN(date.getTime())) return formatMatchDateTime(fecha, hora);
  const formatted = new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: SYNC_TIMEZONE,
  }).format(date);
  return formatted.replace(",", " ·");
}

function formatResultado(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

const PORRA_LABELS = {
  1: "1",
  X: "X",
  2: "2",
};

function formatPorraPick(value) {
  if (value === null || value === undefined || value === "") return "—";
  return PORRA_LABELS[value] || formatResultado(value);
}

function validateData(data) {
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error("El fichero no contiene datos de clasificación válidos.");
  }
  data.forEach((entry, index) => {
    const required = ["posicion", "nombre", "aciertos", "puntos"];
    const missing = required.filter((field) => entry[field] === undefined);
    if (missing.length > 0) {
      throw new Error(`Entrada ${index + 1} incompleta: faltan ${missing.join(", ")}.`);
    }
  });
}

function loadInlineClasificacion() {
  const node = document.getElementById("clasificacion-data");
  if (!node || !node.textContent.trim()) return null;
  const data = JSON.parse(node.textContent);
  validateData(data);
  return data;
}

function loadEmbeddedClasificacion() {
  if (!window.__CLASIFICACION__) return null;
  validateData(window.__CLASIFICACION__);
  return window.__CLASIFICACION__;
}

async function fetchClasificacion() {
  const response = await fetch(DATA_URL);
  if (!response.ok) {
    throw new Error(`No se pudo acceder a clasificacion.json (${response.status}).`);
  }
  const data = await response.json();
  validateData(data);
  return data;
}

function loadClasificacionSync() {
  for (const source of [loadInlineClasificacion, loadEmbeddedClasificacion]) {
    try {
      const data = source();
      if (data) return data;
    } catch {
      continue;
    }
  }
  return null;
}

async function loadClasificacion() {
  const localData = loadClasificacionSync();
  if (localData) return localData;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchClasificacion();
  throw new Error("No se encontraron datos. Ejecuta calcular_clasificacion.py para actualizar.");
}

function validatePremios(data) {
  if (!Array.isArray(data)) {
    throw new Error("El fichero no contiene datos de premios válidos.");
  }
  data.forEach((entry, index) => {
    const required = ["posicion", "nombre", "premio_total"];
    const missing = required.filter((field) => entry[field] === undefined);
    if (missing.length > 0) {
      throw new Error(`Premio ${index + 1} incompleto: faltan ${missing.join(", ")}.`);
    }
  });
}

function loadInlinePremios() {
  const node = document.getElementById("premios-data");
  if (!node || !node.textContent.trim()) return null;
  const data = JSON.parse(node.textContent);
  validatePremios(data);
  return data;
}

function loadEmbeddedPremios() {
  if (!window.__PREMIOS__) return null;
  validatePremios(window.__PREMIOS__);
  return window.__PREMIOS__;
}

async function fetchPremios() {
  const response = await fetch(PREMIOS_URL);
  if (!response.ok) {
    throw new Error(`No se pudo acceder a premios.json (${response.status}).`);
  }
  const data = await response.json();
  validatePremios(data);
  return data;
}

function loadPremiosSync() {
  for (const source of [loadInlinePremios, loadEmbeddedPremios]) {
    try {
      const data = source();
      if (data) return data;
    } catch {
      continue;
    }
  }
  return null;
}

async function loadPremios() {
  const localData = loadPremiosSync();
  if (localData) return localData;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) {
    try {
      return await fetchPremios();
    } catch {
      return [];
    }
  }
  return [];
}

function loadEmbeddedPartidos() {
  return window.__PARTIDOS__ || null;
}

async function fetchPartidos() {
  const response = await fetch(PARTIDOS_URL);
  if (!response.ok) throw new Error(`No se pudo acceder a partidos.json (${response.status}).`);
  return response.json();
}

async function loadPartidos() {
  const embedded = loadEmbeddedPartidos();
  if (embedded) return embedded;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchPartidos();
  return null;
}

function loadEmbeddedResultados() {
  return window.__RESULTADOS__ || null;
}

async function fetchResultados() {
  const response = await fetch(RESULTADOS_URL);
  if (!response.ok) throw new Error(`No se pudo acceder a resultados.json (${response.status}).`);
  return response.json();
}

async function loadResultados() {
  const embedded = loadEmbeddedResultados();
  if (embedded) return embedded;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchResultados();
  return null;
}

function loadEmbeddedMarcadores() {
  return window.__MARCADORES__ || null;
}

async function fetchMarcadores() {
  const response = await fetch(MARCADORES_URL);
  if (!response.ok) throw new Error(`No se pudo acceder a marcadores.json (${response.status}).`);
  return response.json();
}

async function loadMarcadores() {
  const embedded = loadEmbeddedMarcadores();
  if (embedded) return embedded;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchMarcadores();
  return null;
}

function loadEmbeddedEvolucion() {
  return window.__EVOLUCION__ || null;
}

async function fetchEvolucion() {
  const response = await fetch(`./evolucion.json?v=${BUILD}`);
  if (!response.ok) throw new Error(`No se pudo acceder a evolucion.json (${response.status}).`);
  return response.json();
}

async function loadEvolucion() {
  const embedded = loadEmbeddedEvolucion();
  if (embedded) return embedded;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchEvolucion();
  return null;
}

function loadEmbeddedParticipantes() {
  return window.__PARTICIPANTES__ || null;
}

async function fetchParticipantes() {
  const response = await fetch(PARTICIPANTES_URL);
  if (!response.ok) {
    throw new Error(`No se pudo acceder a participantes.json (${response.status}).`);
  }
  return response.json();
}

async function fetchStatus() {
  const response = await fetch(STATUS_URL);
  if (!response.ok) {
    throw new Error(`No se pudo acceder a status.json (${response.status}).`);
  }
  return response.json();
}

async function loadStatus() {
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (!canFetch) return null;
  try {
    return await fetchStatus();
  } catch {
    return null;
  }
}

async function loadParticipantes() {
  const embedded = loadEmbeddedParticipantes();
  if (embedded) return embedded;
  const canFetch = window.location.protocol === "http:" || window.location.protocol === "https:";
  if (canFetch) return fetchParticipantes();
  return null;
}

async function getParticipante(nombre) {
  if (!appData.participantes) {
    throw new Error("No se cargaron los datos de participantes.");
  }
  const participante = appData.participantes[nombre];
  if (!participante) {
    throw new Error(`No se encontraron pronósticos para ${nombre}.`);
  }
  return participante;
}

const PICK_INFO = {
  "1": { label: "1", short: "1" },
  "X": { label: "X", short: "X" },
  "2": { label: "2", short: "2" },
};

/* ── Match status helpers ── */

function isEliminatoriaFase(fase) {
  return Boolean(fase && fase !== "grupos");
}

function normalizePick(pick, fase) {
  if (pick === null || pick === undefined) {
    return { resultado: null, clasifica: null };
  }
  if (typeof pick === "object") {
    return {
      resultado: pick.resultado ?? null,
      clasifica: pick.clasifica ?? null,
    };
  }
  if (isEliminatoriaFase(fase)) {
    return { resultado: pick, clasifica: null };
  }
  return { resultado: pick, clasifica: null };
}

function normalizeResultado(resultado, fase) {
  if (resultado === null || resultado === undefined) {
    return { resultado: null, clasifica: null };
  }
  if (typeof resultado === "object") {
    return {
      resultado: resultado.resultado ?? null,
      clasifica: resultado.clasifica ?? null,
    };
  }
  if (isEliminatoriaFase(fase)) {
    return { resultado: resultado, clasifica: null };
  }
  return { resultado: resultado, clasifica: null };
}

function isMatchPending(resultado) {
  return resultado === null || resultado === undefined;
}

function isProximosPartido(partido, index, resultados) {
  return partido.fase === PROXIMOS_FASE && isMatchPending(resultados[index]);
}

function countProximosPartidos(partidos, resultados) {
  return partidos.filter((p, i) => isProximosPartido(p, i, resultados)).length;
}

function isMatchPlayed(resultado, fase) {
  if (resultado === null || resultado === undefined) return false;
  if (isEliminatoriaFase(fase)) {
    return normalizeResultado(resultado, fase).resultado !== null;
  }
  return true;
}

function clasificaSideLabel(clasifica, partido) {
  if (clasifica === "1" || clasifica === "2") return clasifica;
  return "—";
}

function formatPickValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  const texto = String(value).trim().toUpperCase();
  if (texto === "1" || texto === "X" || texto === "2") return texto;
  return texto;
}

function formatPickDisplay(pick, fase, partido) {
  const p = normalizePick(pick, fase);
  if (!isEliminatoriaFase(fase)) {
    return formatPickValue(p.resultado);
  }
  const res = formatPickValue(p.resultado);
  const cls = p.clasifica ? clasificaSideLabel(p.clasifica, partido) : "—";
  return `${res} · ↑ ${cls}`;
}

function formatResultDisplay(resultado, fase, partido) {
  const r = normalizeResultado(resultado, fase);
  if (!isEliminatoriaFase(fase)) {
    return formatPickValue(r.resultado);
  }
  const res = formatPickValue(r.resultado);
  const cls = r.clasifica ? clasificaSideLabel(r.clasifica, partido) : "—";
  return `${res} · ↑ ${cls}`;
}

function scoreMatchBets(pronostico, resultado, fase) {
  if (!isMatchPlayed(resultado, fase)) {
    return { hits: 0, misses: 0, pending: isEliminatoriaFase(fase) ? 2 : 1 };
  }

  const p = normalizePick(pronostico, fase);
  const r = normalizeResultado(resultado, fase);

  if (!isEliminatoriaFase(fase)) {
    return p.resultado === r.resultado
      ? { hits: 1, misses: 0, pending: 0 }
      : { hits: 0, misses: 1, pending: 0 };
  }

  let hits = 0;
  let misses = 0;
  let pending = 0;

  if (p.resultado && r.resultado) {
    if (p.resultado === r.resultado) hits++;
    else misses++;
  } else if (r.resultado) {
    pending++;
  }

  if (p.clasifica && r.clasifica) {
    if (p.clasifica === r.clasifica) hits++;
    else misses++;
  } else if (r.clasifica) {
    pending++;
  }

  return { hits, misses, pending };
}

function getMatchStatus(pronostico, resultado, fase = "grupos") {
  if (!isMatchPlayed(resultado, fase)) return "pending";
  const { hits, misses, pending } = scoreMatchBets(pronostico, resultado, fase);
  if (hits > 0 && misses === 0 && pending === 0) return "hit";
  if (hits > 0 && misses > 0) return "partial";
  return "miss";
}

function countPlayedMatches(resultados, partidos = appData.partidos || []) {
  return resultados.filter((r, i) => isMatchPlayed(r, partidos[i]?.fase)).length;
}

function countEvaluatedBets(resultados, partidos = appData.partidos || []) {
  let total = 0;
  resultados.forEach((r, i) => {
    if (!isMatchPlayed(r, partidos[i]?.fase)) return;
    const nr = normalizeResultado(r, partidos[i]?.fase);
    if (isEliminatoriaFase(partidos[i]?.fase)) {
      if (nr.resultado !== null) total++;
      if (nr.clasifica !== null) total++;
    } else {
      total++;
    }
  });
  return total;
}

function calcPrecision(aciertos, resultados, partidos = appData.partidos || []) {
  const jugados = countEvaluatedBets(resultados, partidos);
  if (jugados === 0) return 0;
  return Math.round((aciertos / jugados) * 100);
}

/* ── Navigation ── */

function showView(view) {
  elements.viewHome.classList.remove("view--active", "view--exit");
  elements.viewParticipant.classList.remove("view--active", "view--exit");
  elements.viewParticipant.hidden = true;
  if (view === "participant") {
    elements.viewParticipant.hidden = false;
    requestAnimationFrame(() => {
      elements.viewParticipant.classList.add("view--active");
    });
  } else {
    requestAnimationFrame(() => {
      elements.viewHome.classList.add("view--active");
    });
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function openParticipant(nombre) {
  const entry = appData.clasificacion.find((e) => e.nombre === nombre);
  if (!entry || !elements.predList) return;

  showView("participant");
  elements.predList.innerHTML = `
    <div class="pred-loading">
      <div class="loading__ball" aria-hidden="true"></div>
      <p>Cargando pronósticos...</p>
    </div>
  `;

  try {
    const participante = await getParticipante(nombre);
    renderParticipantDetail(entry, participante);
  } catch (error) {
    elements.predList.innerHTML = `
      <div class="pred-error">
        <span aria-hidden="true">⚠</span>
        <p>${error instanceof Error ? error.message : "Error al cargar pronósticos."}</p>
      </div>
    `;
    renderParticipantDetailHeader(entry);
  }
}

/* ── Rendering: home ── */

function calcularEstadisticasPartidos() {
  const partidos = appData.partidos || [];
  const resultados = appData.resultados || [];
  const total = partidos.length;
  const finalizados = countPlayedMatches(resultados, partidos);
  const restantes = total - finalizados;
  const puntosPorDisputar = partidos.reduce((acc, p, i) => {
    const resultado = resultados[i];
    return resultado === null || resultado === undefined ? acc + (p.peso || 0) : acc;
  }, 0);
  const puntosConsumidos = PUNTOS_MAXIMOS - puntosPorDisputar;
  return { total, finalizados, restantes, puntosPorDisputar, puntosConsumidos };
}

function renderStats(data, status) {
  const lastSync = status?.lastWorkflowRun || null;
  const syncOk = Boolean(lastSync && status?.workflowStatus === "ok");

  const stats = {
    actualizacion: lastSync ? formatSyncDate(lastSync) : "—",
    "actualizacion-relativa": lastSync ? formatRelativeTime(lastSync) : "—",
  };

  elements.stats.querySelectorAll("[data-stat]").forEach((node) => {
    const key = node.dataset.stat;
    if (key === "error-sincronizacion") return;
    if (stats[key] !== undefined) node.textContent = stats[key];
  });

  const errorNode = elements.stats.querySelector('[data-stat="error-sincronizacion"]');
  if (errorNode) {
    if (syncOk) {
      errorNode.hidden = true;
      errorNode.textContent = "";
    } else {
      errorNode.hidden = false;
      errorNode.textContent = "Error de sincronización";
    }
  }
}

function renderProgress() {
  const { total, finalizados, restantes, puntosPorDisputar, puntosConsumidos } =
    calcularEstadisticasPartidos();
  if (!total) return;

  const pctPartidos = Math.round((finalizados / total) * 100);
  const pctPuntos = Math.round((puntosConsumidos / PUNTOS_MAXIMOS) * 100);

  const section = document.getElementById("mundial-progress");
  if (!section) return;

  const valores = {
    "partidos-jugados": finalizados,
    "partidos-total": total,
    "partidos-restantes": restantes,
    "puntos-consumidos": puntosConsumidos,
    "puntos-maximos-total": PUNTOS_MAXIMOS,
    "puntos-por-disputar": puntosPorDisputar,
  };

  section.querySelectorAll("[data-stat]").forEach((node) => {
    const key = node.dataset.stat;
    if (valores[key] !== undefined) node.textContent = valores[key];
  });

  const trackPartidos = document.getElementById("progress-track-partidos");
  const fillPartidos = document.getElementById("progress-fill-partidos");
  const trackPuntos = document.getElementById("progress-track-puntos");
  const fillPuntos = document.getElementById("progress-fill-puntos");

  if (trackPartidos) trackPartidos.setAttribute("aria-valuenow", pctPartidos);
  if (trackPuntos) trackPuntos.setAttribute("aria-valuenow", pctPuntos);

  requestAnimationFrame(() => {
    if (fillPartidos) fillPartidos.style.width = `${pctPartidos}%`;
    if (fillPuntos) fillPuntos.style.width = `${pctPuntos}%`;
  });
}

/* ── Rendering: evolución (storytelling) ── */

const evolucionState = { showIA: false, selectedPlayers: [], hoverPlayer: null };
const EVENT_LABELS = {
  primer_lider: "Primer líder",
  cambio_lider: "Cambio de líder",
  empate_lider: "Empate en cabeza",
  adelantamiento: "Adelantamiento",
  adelantamiento_multiple: "Gran remontada",
  mayor_remontada: "Mayor remontada",
  mayor_ventaja: "Mayor ventaja",
  partido_clave: "Partido clave",
  campeon_matematico: "Campeón matemático",
};

function evolVisibles(evol) {
  return evol.participantes.filter((p) => evolucionState.showIA || !p.es_ia);
}

function evolPlayer(evol, nombre) {
  return evol.participantes.find((p) => p.nombre === nombre) || null;
}

/* ── Bump chart helpers ── */

/**
 * Posición del jugador tras el partido `step` (1-indexed).
 * Usa posicion_humanos cuando solo se muestran humanos.
 */
function bumpPosAt(p, step) {
  if (!p || step < 1 || step > p.detalle.length) return null;
  const d = p.detalle[step - 1];
  return (evolucionState.showIA ? d.posicion : d.posicion_humanos) ?? d.posicion;
}

/** Posición final (menor = mejor). Usada para ordenar el roster. */
function evolFinal(p) {
  return bumpPosAt(p, p.detalle.length) ?? 99;
}

function setupEvolucionToggle() {
  const input = elements.iaToggleInput;
  if (!input || input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  input.checked = evolucionState.showIA;
  input.addEventListener("change", () => {
    evolucionState.showIA = input.checked;
    evolucionState.selectedPlayers = [];
    evolucionState.hoverPlayer = null;
    renderEvolucion();
  });
}

function renderEvolucion() {
  const evol = appData.evolucion;
  const section = elements.evolucionSection;
  if (!section) return;
  if (!evol || !Array.isArray(evol.participantes) || (evol.partidos_jugados || 0) < 1) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  setupEvolucionToggle();
  renderEvolucionRoster(evol);
  drawEvolucionChart(evol);
  applyEvolucionHighlight();
}

/** Hitos del eje X — infografía por fases del torneo. */
const EVOL_MILESTONES = [
  { id: "inicio", label: "Inicio", orden: 0 },
  { id: "mitad_grupos", label: "Mitad grupos", fase: "grupos", at: "mid" },
  { id: "fin_grupos", label: "Fin grupos", fase: "grupos", at: "end" },
  { id: "octavos", label: "Octavos", fase: "octavos", at: "end" },
  { id: "cuartos", label: "Cuartos", fase: "cuartos", at: "end" },
  { id: "semifinales", label: "Semifinales", fase: "semifinales", at: "end" },
  { id: "final", label: "Final", fase: "final", at: "end" },
];

function resolveMilestoneOrden(evol, milestone) {
  if (milestone.orden === 0) return 0;
  const inPhase = evol.partidos.filter((p) => p.fase === milestone.fase);
  if (!inPhase.length) return null;
  if (milestone.at === "mid") {
    return inPhase[Math.floor((inPhase.length - 1) / 2)].orden;
  }
  return inPhase[inPhase.length - 1].orden;
}

/** Hitos visibles según el progreso actual del torneo. */
function buildEvolMilestones(evol) {
  const resolved = [];
  for (const def of EVOL_MILESTONES) {
    const orden = resolveMilestoneOrden(evol, def);
    if (orden === null) continue;
    if (def.orden !== 0 && orden > evol.partidos_jugados) continue;
    resolved.push({ ...def, orden });
  }
  // Evitar hitos duplicados (p. ej. mitad = fin con pocos partidos)
  const seen = new Set();
  return resolved.filter((m) => {
    if (seen.has(m.orden)) return false;
    seen.add(m.orden);
    return true;
  });
}

/** Posición en un hito. Inicio = línea de salida (centro visual). */
function bumpPosAtMilestone(p, orden, nPos) {
  if (orden === 0) return Math.ceil(nPos / 2);
  return bumpPosAt(p, orden);
}

function evolPremio(nombre) {
  const entry = (appData.premios || []).find((x) => x.nombre === nombre);
  return entry ? entry.premio_total : null;
}

/** Curva Bézier suave entre hitos (estilo infografía deportiva). */
function makeSmoothPath(pts, tension = 0.42) {
  if (!pts.length) return "";
  if (pts.length === 1) return `M ${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  let d = `M ${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i - 1];
    const p1 = pts[i];
    const dx = p1.x - p0.x;
    const cx1 = p0.x + dx * tension;
    const cx2 = p1.x - dx * tension;
    d += ` C ${cx1.toFixed(1)},${p0.y.toFixed(1)} ${cx2.toFixed(1)},${p1.y.toFixed(1)} ${p1.x.toFixed(1)},${p1.y.toFixed(1)}`;
  }
  return d;
}

function renderEvolucionRoster(evol) {
  const roster = elements.evolucionRoster;
  if (!roster) return;
  // Ordenar por posición ascendente (1º primero)
  const visibles = [...evolVisibles(evol)].sort((a, b) => evolFinal(a) - evolFinal(b));
  roster.innerHTML = visibles
    .map(
      (p) => `
      <button class="evol-chip" data-player="${p.nombre}" type="button" role="listitem" style="--chip:${p.color}">
        <span class="evol-chip__avatar">${p.inicial}</span>
        <span class="evol-chip__name">${p.nombre}</span>
        <span class="evol-chip__pts">${evolFinal(p)}º</span>
      </button>`
    )
    .join("");

  roster.querySelectorAll(".evol-chip").forEach((chip) => {
    const name = chip.dataset.player;
    chip.addEventListener("mouseenter", () => setEvolucionHover(name));
    chip.addEventListener("mouseleave", () => clearEvolucionHover());
    chip.addEventListener("click", () => toggleEvolucionPlayer(name));
  });
}

function drawEvolucionChart(evol) {
  const chart = elements.evolucionChart;
  if (!chart) return;

  const milestones = buildEvolMilestones(evol);
  if (milestones.length < 2) return;

  const visibles = evolVisibles(evol);
  const nPos = visibles.length;
  const nM = milestones.length;

  const width = Math.max(Math.round(chart.getBoundingClientRect().width) || 680, 280);
  const isMobile = width < 560;
  const rowH = isMobile ? 52 : 64;
  const mL = isMobile ? 36 : 44;
  const mR = isMobile ? 36 : 44;
  const mT = 24;
  const mB = 36;
  const plotH = rowH * Math.max(nPos - 1, 1);
  const totalH = plotH + mT + mB;
  const plotW = width - mL - mR;

  const xAt = (idx) => mL + (idx / (nM - 1)) * plotW;
  const yAt = (pos) => mT + ((pos - 1) / Math.max(nPos - 1, 1)) * plotH;

  const milestoneLayout = milestones.map((m, idx) => ({
    ...m,
    idx,
    x: xAt(idx),
  }));

  const getY = (nombre, orden) => {
    const p = evolPlayer(evol, nombre);
    const pos = bumpPosAtMilestone(p, orden, nPos);
    if (pos == null) return null;
    return yAt(pos);
  };

  const grid = Array.from({ length: nPos }, (_, i) => {
    const pos = i + 1;
    const y = yAt(pos);
    return `<line class="evol-grid__line" x1="${mL}" y1="${y.toFixed(1)}" x2="${mL + plotW}" y2="${y.toFixed(1)}" />
            <text class="evol-grid__label evol-grid__label--pos" x="${(mL - 6).toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="end">${pos}º</text>`;
  }).join("");

  const axisLabels = milestoneLayout
    .map((m) => `<text class="evol-milestone__label" x="${m.x.toFixed(1)}" y="${(totalH - 10).toFixed(1)}" text-anchor="middle">${m.label}</text>`)
    .join("");

  const axisTicks = milestoneLayout
    .map((m) => `<line class="evol-milestone__tick" x1="${m.x.toFixed(1)}" y1="${mT}" x2="${m.x.toFixed(1)}" y2="${(mT + plotH).toFixed(1)}" />`)
    .join("");

  const firstM = milestones[0];
  const lastM = milestones[milestones.length - 1];
  const avR = isMobile ? 12 : 14;

  const lines = visibles.map((p) => {
    const pts = milestones
      .map((m, idx) => {
        const y = getY(p.nombre, m.orden);
        return y != null ? { x: xAt(idx), y } : null;
      })
      .filter(Boolean);
    const d = makeSmoothPath(pts);
    if (!d) return "";
    return `<path class="evol-line evol-line--visible" data-player="${p.nombre}"
        fill="none" stroke="${p.color}" style="color:${p.color}" d="${d}" />
      <path class="evol-line evol-line--hit" data-player="${p.nombre}"
        fill="none" stroke="transparent" stroke-width="18" d="${d}" />`;
  }).join("");

  const avatars = visibles.map((p) => {
    const yStart = getY(p.nombre, firstM.orden);
    const yEnd = getY(p.nombre, lastM.orden);
    if (yStart == null || yEnd == null) return "";
    const xStart = xAt(0);
    const xEnd = xAt(nM - 1);
    return `<g class="evol-avatar evol-avatar--start" data-player="${p.nombre}">
        <circle class="evol-avatar__bg" cx="${xStart.toFixed(1)}" cy="${yStart.toFixed(1)}" r="${avR}" style="--c:${p.color}" />
        <text class="evol-avatar__txt" x="${xStart.toFixed(1)}" y="${(yStart + 4).toFixed(1)}" text-anchor="middle">${p.inicial}</text>
      </g>
      <g class="evol-avatar evol-avatar--end" data-player="${p.nombre}">
        <circle class="evol-avatar__bg" cx="${xEnd.toFixed(1)}" cy="${yEnd.toFixed(1)}" r="${avR}" style="--c:${p.color}" />
        <text class="evol-avatar__txt" x="${xEnd.toFixed(1)}" y="${(yEnd + 4).toFixed(1)}" text-anchor="middle">${p.inicial}</text>
      </g>`;
  }).join("");

  chart.innerHTML = `<svg class="evol-svg evol-svg--infographic"
      viewBox="0 0 ${width} ${totalH}"
      width="100%" height="${totalH}"
      preserveAspectRatio="xMidYMid meet"
      role="img" aria-label="Evolución de la clasificación por fases">
    <g class="evol-grid">${grid}</g>
    <g class="evol-milestones">${axisTicks}${axisLabels}</g>
    <g class="evol-lines">${lines}</g>
    <g class="evol-avatars">${avatars}</g>
  </svg>`;

  bindEvolucionInteractions(evol, { milestones: milestoneLayout, mL, mT, plotW, plotH, getY, xAt, nM });
}

function bindEvolucionInteractions(evol, geo) {
  const chart = elements.evolucionChart;

  const nearestMilestone = (mx) => {
    let best = geo.milestones[0];
    let bestDist = Infinity;
    geo.milestones.forEach((m) => {
      const d = Math.abs(mx - m.x);
      if (d < bestDist) { bestDist = d; best = m; }
    });
    return best;
  };

  chart.querySelectorAll(".evol-line--hit").forEach((node) => {
    const name = node.dataset.player;
    node.addEventListener("mouseenter", () => setEvolucionHover(name));
    node.addEventListener("mouseleave", () => {
      clearEvolucionHover();
      hideEvolucionTooltip();
    });
    node.addEventListener("mousemove", (event) => {
      const rect = chart.querySelector(".evol-svg").getBoundingClientRect();
      const mx = geo.mL + ((event.clientX - rect.left) / rect.width) * geo.plotW;
      const milestone = nearestMilestone(mx);
      showMilestoneTooltip(evol, milestone, name, geo.milestones, event);
    });
    node.addEventListener("click", () => toggleEvolucionPlayer(name));
  });

  chart.querySelectorAll(".evol-avatar").forEach((node) => {
    const name = node.dataset.player;
    node.addEventListener("mouseenter", () => setEvolucionHover(name));
    node.addEventListener("mouseleave", () => clearEvolucionHover());
    node.addEventListener("click", () => toggleEvolucionPlayer(name));
  });
}

function evolEventsInSegment(evol, fromOrden, toOrden, playerName) {
  return (evol.eventos || []).filter((ev) => {
    if (ev.orden <= fromOrden || ev.orden > toOrden) return false;
    if (playerName && ev.protagonista && ev.protagonista !== playerName) return false;
    return true;
  });
}

function showMilestoneTooltip(evol, milestone, playerName, milestones, event) {
  const tip = elements.evolucionTooltip;
  if (!tip) return;
  const p = evolPlayer(evol, playerName);
  if (!p) return;

  const visibles = evolVisibles(evol);
  const nPos = visibles.length;
  const pos = bumpPosAtMilestone(p, milestone.orden, nPos);
  const orden = milestone.orden;
  const d = orden > 0 ? p.detalle[orden - 1] : null;
  const acc = d ? d.acumulado : 0;

  const leaderAcc = orden > 0
    ? Math.max(...visibles.map((x) => x.detalle[orden - 1]?.acumulado ?? 0))
    : 0;
  const diff = leaderAcc - acc;
  const diffStr = orden === 0 ? "—" : diff === 0 ? "Líder" : `-${diff} pts`;
  const premio = evolPremio(playerName);

  const mIdx = milestone.idx ?? 0;
  const prevOrden = mIdx > 0 ? milestones[mIdx - 1].orden : 0;
  const events = evolEventsInSegment(evol, prevOrden, orden, playerName);
  const eventsHtml = events.length
    ? `<div class="evol-tip__events">${events.slice(0, 3).map((ev) =>
        `<div class="evol-tip__event-row"><span class="evol-tip__badge evol-tip__badge--sm">${EVENT_LABELS[ev.tipo] || ev.titulo}</span><span>${ev.titulo}</span></div>`
      ).join("")}</div>`
    : "";

  tip.innerHTML = `
    <div class="evol-tip__head">
      <span class="evol-tip__title">${milestone.label}</span>
    </div>
    <div class="evol-tip__player">
      <span class="evol-tip__avatar" style="--c:${p.color}">${p.inicial}</span>
      <span class="evol-tip__pname">${p.nombre}</span>
      <span class="evol-tip__pos evol-tip__pos--${pos === 1 ? "lead" : "rest"}">${pos != null ? pos + "º" : "—"}</span>
    </div>
    <div class="evol-tip__grid">
      <div><span class="evol-tip__k">Acumulado</span><span class="evol-tip__v">${orden === 0 ? "0" : acc} pts</span></div>
      <div><span class="evol-tip__k">Vs líder</span><span class="evol-tip__v evol-tip__v--diff ${diff === 0 && orden > 0 ? "is-lead" : ""}">${diffStr}</span></div>
      ${premio != null ? `<div><span class="evol-tip__k">Premio</span><span class="evol-tip__v">${formatEuro(premio)}</span></div>` : ""}
      ${d ? `<div><span class="evol-tip__k">Pronóstico</span><span class="evol-tip__v">${evolPickLabel(d.pronostico)}</span></div>` : ""}
    </div>
    ${eventsHtml}`;
  positionEvolucionTooltip(event);
}

function evolHighlightedSet() {
  if (evolucionState.selectedPlayers.length > 0) {
    return new Set(evolucionState.selectedPlayers);
  }
  if (evolucionState.hoverPlayer) {
    return new Set([evolucionState.hoverPlayer]);
  }
  return null;
}

function toggleEvolucionPlayer(name) {
  const idx = evolucionState.selectedPlayers.indexOf(name);
  if (idx >= 0) {
    evolucionState.selectedPlayers.splice(idx, 1);
  } else {
    evolucionState.selectedPlayers.push(name);
  }
  evolucionState.hoverPlayer = null;
  applyEvolucionHighlight();
}

function setEvolucionHover(name) {
  if (evolucionState.selectedPlayers.length > 0) return;
  evolucionState.hoverPlayer = name;
  applyEvolucionHighlight();
}

function clearEvolucionHover() {
  if (evolucionState.selectedPlayers.length > 0) return;
  evolucionState.hoverPlayer = null;
  applyEvolucionHighlight();
}

function applyEvolucionHighlight() {
  const chart = elements.evolucionChart;
  const roster = elements.evolucionRoster;
  if (!chart) return;
  const highlighted = evolHighlightedSet();

  const setState = (node) => {
    const name = node.dataset.player;
    const isOn = highlighted && highlighted.has(name);
    const isDim = highlighted && !isOn && name !== "";
    node.classList.toggle("is-active", Boolean(isOn));
    node.classList.toggle("is-dim", Boolean(isDim));
  };
  chart.querySelectorAll(".evol-line--visible").forEach(setState);
  chart.querySelectorAll(".evol-avatar").forEach(setState);
  if (roster) roster.querySelectorAll(".evol-chip").forEach(setState);
}

function evolPickLabel(pick) {
  if (pick === null || pick === undefined || pick === "") return "—";
  if (typeof pick === "object") {
    const res = formatPickValue(pick.resultado);
    const cls = pick.clasifica === "1" || pick.clasifica === "2" ? pick.clasifica : "—";
    return `${res} · Clasifica: ${cls}`;
  }
  return formatPickValue(pick);
}

function positionEvolucionTooltip(event) {
  const tip = elements.evolucionTooltip;
  const panel = elements.evolucionPanel;
  if (!tip || !panel) return;
  tip.hidden = false;
  const panelRect = panel.getBoundingClientRect();
  const tipRect = tip.getBoundingClientRect();
  let left = event.clientX - panelRect.left - tipRect.width / 2;
  let top = event.clientY - panelRect.top - tipRect.height - 14;
  left = Math.min(Math.max(left, 6), panelRect.width - tipRect.width - 6);
  if (top < 4) top = event.clientY - panelRect.top + 18;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

function hideEvolucionTooltip() {
  if (elements.evolucionTooltip) elements.evolucionTooltip.hidden = true;
}

let evolResizeTimer = null;
window.addEventListener("resize", () => {
  if (!appData.evolucion) return;
  clearTimeout(evolResizeTimer);
  evolResizeTimer = setTimeout(() => {
    if (elements.evolucionSection && !elements.evolucionSection.hidden) drawEvolucionChart(appData.evolucion);
    applyEvolucionHighlight();
  }, 180);
});

function createPodiumPlayer(entry) {
  const pos = entry.posicion;
  const article = document.createElement("article");
  article.className = `podium-player podium-player--${pos}`;
  article.setAttribute("role", "listitem");

  article.innerHTML = `
    <div class="podium-player__glow" aria-hidden="true"></div>
    <div class="podium-player__body">
      <span class="podium-player__medal" aria-hidden="true">${getMedal(pos)}</span>
      <div class="podium-player__avatar" data-player="${entry.nombre}">${getInitials(entry.nombre)}</div>
      <h3 class="podium-player__name" data-player="${entry.nombre}">${entry.nombre}</h3>
      <span class="podium-player__points">${entry.puntos}</span>
      <span class="podium-player__meta">${entry.aciertos} aciertos</span>
    </div>
    <div class="podium-player__stand">
      <div class="podium-player__stand-top"></div>
      <div class="podium-player__stand-face"></div>
      <span class="podium-player__rank">${pos}º</span>
    </div>
  `;

  article.querySelectorAll("[data-player]").forEach((el) => {
    el.addEventListener("click", () => openParticipant(entry.nombre));
  });
  return article;
}

function renderPodium(data) {
  const topThree = data.filter((e) => e.posicion <= 3);
  elements.podium.innerHTML = "";
  if (topThree.length === 0) {
    elements.podiumSection.hidden = true;
    return;
  }
  elements.podiumSection.hidden = false;
  PODIUM_ORDER
    .map((pos) => topThree.find((e) => e.posicion === pos))
    .filter(Boolean)
    .forEach((entry) => elements.podium.appendChild(createPodiumPlayer(entry)));
}

function createPremioRow(entry, index) {
  const pos = entry.posicion;
  const row = document.createElement("article");
  const topClass = pos <= 3 ? ` premio-row--top premio-row--pos-${pos}` : "";
  row.className = `premio-row${topClass}`;
  row.setAttribute("role", "listitem");
  row.style.animationDelay = `${0.04 * index}s`;

  row.innerHTML = `
    <span class="premio-row__pos" aria-label="Posición ${pos}">${formatPremioPosition(pos)}</span>
    <span class="premio-row__name">${entry.nombre}</span>
    <span class="premio-row__amount">${formatEuro(entry.premio_total)}</span>
  `;

  return row;
}

function renderPremios(data) {
  if (!elements.premiosList || !elements.premiosSection) return;
  elements.premiosList.innerHTML = "";
  if (!data || data.length === 0) {
    elements.premiosSection.hidden = true;
    return;
  }
  elements.premiosSection.hidden = false;
  data.forEach((entry, i) => {
    elements.premiosList.appendChild(createPremioRow(entry, i));
  });
}

function createTableRow(entry, index) {
  const row = document.createElement("tr");
  const pos = entry.posicion;
  if (pos <= 3) {
    row.classList.add("row--top", `row--pos-${pos}`);
  }
  row.style.animationDelay = `${0.04 * index}s`;

  row.innerHTML = `
    <td class="col-pos">${formatPosition(entry.posicion)}</td>
    <td class="col-avatar"><div class="player-avatar">${getInitials(entry.nombre)}</div></td>
    <td class="col-name">${entry.nombre}</td>
    <td class="num">${entry.aciertos}</td>
    <td class="num col-points">${entry.puntos}</td>
    <td><span class="trend-icon" title="Ver detalle">→</span></td>
  `;

  row.addEventListener("click", () => openParticipant(entry.nombre));
  return row;
}

function createMobileRow(entry, index) {
  const row = document.createElement("article");
  const pos = entry.posicion;
  const topClass = pos <= 3 ? ` mobile-row--top mobile-row--pos-${pos}` : "";
  row.className = `mobile-row${topClass}`;
  row.setAttribute("role", "listitem");
  row.style.animationDelay = `${0.04 * index}s`;

  row.innerHTML = `
    <div class="mobile-row__pos">${formatPosition(entry.posicion)}</div>
    <div class="player-avatar">${getInitials(entry.nombre)}</div>
    <div class="mobile-row__info">
      <div class="mobile-row__name">${entry.nombre}</div>
      <div class="mobile-row__meta">${entry.aciertos} aciertos</div>
    </div>
    <div class="mobile-row__points">${entry.puntos}</div>
  `;

  row.addEventListener("click", () => openParticipant(entry.nombre));
  return row;
}

function renderTable(data) {
  elements.leaderboardBody.innerHTML = "";
  elements.mobileCards.innerHTML = "";
  data.forEach((entry, i) => {
    elements.leaderboardBody.appendChild(createTableRow(entry, i));
    elements.mobileCards.appendChild(createMobileRow(entry, i));
  });
}

/* ── Rendering: participant detail ── */

function buildGroupsMap() {
  return GRUPOS_OFICIALES.map((equipos) => [...equipos].sort((a, b) => a.localeCompare(b, "es")));
}

function getGroupLabel(idx) {
  return `Grupo ${String.fromCharCode(65 + idx)}`;
}

function getGroupTeamsLabel(idx) {
  return GRUPOS_OFICIALES[idx]?.join(" · ") || "";
}

function compareMatchSchedule(a, b) {
  const da = new Date(`${a.partido.fecha}T${a.partido.hora}:00`);
  const db = new Date(`${b.partido.fecha}T${b.partido.hora}:00`);
  return da - db;
}

function sortMatchesBySchedule(matches) {
  return [...matches].sort(compareMatchSchedule);
}

function categorizeFases(partidos, pronosticos, resultados) {
  const fases = {};
  partidos.forEach((p, i) => {
    const key = p.fase === "grupos" ? "grupos" : p.fase;
    if (!fases[key]) fases[key] = [];
    fases[key].push({ partido: p, index: i, pronostico: pronosticos[i] ?? null, resultado: resultados[i] ?? null });
  });
  return fases;
}

function getGroupForMatch(partido, groups) {
  for (let i = 0; i < groups.length; i++) {
    if (groups[i].includes(partido.local) || groups[i].includes(partido.visitante)) return i;
  }
  return -1;
}

function computeGroupStats(groupMatches, pronosticos, resultados) {
  let hits = 0, misses = 0, pending = 0;
  groupMatches.forEach(({ index, partido }) => {
    const stats = scoreMatchBets(
      pronosticos[index],
      resultados[index],
      partido?.fase || "grupos",
    );
    hits += stats.hits;
    misses += stats.misses;
    pending += stats.pending;
  });
  return { hits, misses, pending, total: groupMatches.length };
}

function formatMatchDateShort(fecha) {
  const [, m, d] = fecha.split("-");
  const months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  return `${parseInt(d)} ${months[parseInt(m, 10) - 1]}`;
}

let detailState = { entry: null, participante: null, activeTab: "proximos", activeGroup: 0 };

function renderParticipantDetailHeader(entry) {
  const partidos = appData.partidos || [];
  const resultados = appData.resultados || [];
  const pct = calcPrecision(entry.aciertos, resultados, partidos);
  const jugados = countEvaluatedBets(resultados, partidos);
  const fallos = jugados - entry.aciertos;

  const posClass = entry.posicion <= 3 ? ` detail-hero--pos-${entry.posicion}` : "";
  elements.detailHero.innerHTML = `
    <div class="detail-hero__card${posClass}">
      <div class="detail-hero__glow" aria-hidden="true"></div>
      <div class="detail-hero__top">
        <div class="detail-hero__avatar">${getInitials(entry.nombre)}</div>
        <div class="detail-hero__info">
          <h1 class="detail-hero__name">${entry.nombre}</h1>
          <p class="detail-hero__rank">${formatPosition(entry.posicion)} en la clasificación</p>
        </div>
        <span class="detail-hero__badge">${entry.posicion}º</span>
      </div>
    </div>
  `;

  elements.detailStats.innerHTML = `
    <div class="detail-stat detail-stat--featured">
      <div class="detail-stat__value detail-stat__value--gold">${entry.puntos}</div>
      <div class="detail-stat__label">Puntos</div>
    </div>
    <div class="detail-stat">
      <div class="detail-stat__value">${entry.aciertos}</div>
      <div class="detail-stat__label">Aciertos</div>
    </div>
    <div class="detail-stat">
      <div class="detail-stat__value">${pct}%</div>
      <div class="detail-stat__label">Precisión</div>
      <div class="detail-stat__sub">${entry.aciertos} de ${jugados}</div>
    </div>
    <div class="detail-stat">
      <div class="detail-stat__value">${fallos}</div>
      <div class="detail-stat__label">Fallos</div>
    </div>
  `;
}

function renderGroupNav(groups, pronosticos, resultados, partidos) {
  const fases = categorizeFases(partidos, pronosticos, resultados);
  const pendingCount = countProximosPartidos(partidos, resultados);

  const faseOrder = ["dieciseisavos", "octavos", "cuartos", "semifinales", "tercer_puesto", "final"];
  const fasesElim = faseOrder.filter((f) => fases[f]);

  const tabs = [
    { key: "proximos", label: `Próximos${pendingCount > 0 ? ` (${pendingCount})` : ""}` },
    { key: "grupos", label: "Grupos" },
    ...fasesElim.map((f) => ({ key: f, label: FASE_LABELS[f] })),
  ];

  const tabsHtml = `<div class="detail-tabs">` +
    tabs.map(({ key, label }) =>
      `<button class="detail-tab${detailState.activeTab === key ? " detail-tab--active" : ""}" data-tab="${key}">${label}</button>`
    ).join("") + `</div>`;

  const groupsHtml = groups.map((g, i) => {
    const matches = (fases.grupos || []).filter(({ partido }) => getGroupForMatch(partido, groups) === i);
    const stats = computeGroupStats(matches, pronosticos, resultados);
    const played = stats.hits + stats.misses;
    const pct = played > 0 ? Math.round((stats.hits / played) * 100) : null;
    const isActive = detailState.activeTab === "grupos" && detailState.activeGroup === i;
    return `
      <button class="group-pill${isActive ? " group-pill--active" : ""}" data-group="${i}" title="${getGroupTeamsLabel(i)}">
        <span class="group-pill__label">${getGroupLabel(i)}</span>
        <span class="group-pill__stats">${stats.hits}/${stats.total}</span>
        ${pct !== null ? `<span class="group-pill__pct">${pct}%</span>` : `<span class="group-pill__pct group-pill__pct--empty">—</span>`}
      </button>
    `;
  }).join("");

  const showPills = detailState.activeTab === "grupos";
  elements.detailNav.classList.toggle("detail-nav--tabs-only", !showPills);
  elements.detailNav.innerHTML = `
    ${tabsHtml}
    ${showPills ? `<div class="group-pills">${groupsHtml}</div>` : ""}
  `;

  elements.detailNav.querySelectorAll(".detail-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      detailState.activeTab = btn.dataset.tab;
      renderGroupNav(groups, pronosticos, resultados, partidos);
      renderMatchList();
    });
  });

  elements.detailNav.querySelectorAll(".group-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      detailState.activeGroup = parseInt(btn.dataset.group, 10);
      renderGroupNav(groups, pronosticos, resultados, partidos);
      renderMatchList();
    });
  });
}

function createNextMatchRow(partido, pronostico, index) {
  const row = document.createElement("div");
  const dual = isEliminatoriaFase(partido.fase);
  row.className = `next-row${dual ? " next-row--dual" : ""}`;
  row.style.animationDelay = `${0.04 * index}s`;

  const pickHtml = dual
    ? formatDualPicksHtml(pronostico, partido)
    : `<div class="next-row__picks next-row__picks--single"><div class="next-row__pick-res">${formatPickValue(normalizePick(pronostico, partido.fase).resultado)}</div></div>`;

  row.innerHTML = `
    <div class="next-row__info">
      ${formatWhenSpainHtml(partido)}
      <div class="next-row__teams">
        <div class="next-row__team">
          ${flagImg(partido.local, "flag flag--sm")}
          <span class="next-row__team-name">${partido.local}</span>
        </div>
        <div class="next-row__team">
          ${flagImg(partido.visitante, "flag flag--sm")}
          <span class="next-row__team-name">${partido.visitante}</span>
        </div>
      </div>
    </div>
    ${pickHtml}
  `;

  return row;
}

function clasificaTeamName(clasifica, partido) {
  if (clasifica === "1") return partido?.local || null;
  if (clasifica === "2") return partido?.visitante || null;
  return null;
}

function formatWhenSpainHtml(partido, prefix = "next-row") {
  const time = partido?.hora || "—";
  return `
    <div class="${prefix}__schedule">
      <span class="${prefix}__date">${formatMatchDateShort(partido.fecha)}</span>
      <span class="${prefix}__sched-sep" aria-hidden="true">·</span>
      <span class="${prefix}__time">${time}<span class="${prefix}__time-suffix">h</span></span>
      <span class="${prefix}__sched-sep" aria-hidden="true">·</span>
      <span class="${prefix}__tz">España</span>
    </div>
  `;
}

function formatClasificaFlagHtml(clasifica, partido, flagClass = "flag flag--pick") {
  const team = clasificaTeamName(clasifica, partido);
  if (!team) {
    return `<span class="pick-flag pick-flag--empty" aria-hidden="true">—</span>`;
  }
  return `<span class="pick-flag" title="${team}">${flagImg(team, flagClass)}</span>`;
}

function formatDualPicksHtml(pick, partido, prefix = "next-row") {
  const p = normalizePick(pick, partido.fase);
  const resultado = formatPickValue(p.resultado);
  return `
    <div class="${prefix}__picks">
      <div class="${prefix}__pick-res" title="Resultado del partido">${resultado}</div>
      <div class="${prefix}__pick-cls" title="Clasifica">
        ${formatClasificaFlagHtml(p.clasifica, partido)}
      </div>
    </div>
  `;
}

function puntosPorTipoApuesta(fase, tipo, peso) {
  if (fase === "grupos") return tipo === "resultado" ? 1 : 0;
  if (fase === "tercer_puesto") return tipo === "resultado" ? 13 : 12;
  return Math.floor((peso || 2) / 2);
}

function calcPuntosPartido(pronostico, resultado, partido) {
  const fase = partido.fase || "grupos";
  if (!isMatchPlayed(resultado, fase)) return 0;
  const p = normalizePick(pronostico, fase);
  const r = normalizeResultado(resultado, fase);
  let total = 0;
  if (isEliminatoriaFase(fase)) {
    if (p.resultado && r.resultado && p.resultado === r.resultado) {
      total += puntosPorTipoApuesta(fase, "resultado", partido.peso);
    }
    if (p.clasifica && r.clasifica && p.clasifica === r.clasifica) {
      total += puntosPorTipoApuesta(fase, "clasifica", partido.peso);
    }
  } else if (p.resultado === r.resultado) {
    total = puntosPorTipoApuesta(fase, "resultado", partido.peso);
  }
  return total;
}

function betFieldStatus(pronVal, realVal) {
  if (!realVal || !pronVal) return "pending";
  return pronVal === realVal ? "hit" : "miss";
}

function formatPointsBadge(pts) {
  const cls = pts > 0 ? "mcard__pts--gain" : "mcard__pts--zero";
  const label = pts > 0 ? `+${pts} pt${pts !== 1 ? "s" : ""}` : "0 pts";
  return `<div class="mcard__pts ${cls}">${label}</div>`;
}

function formatComparePickRow(resultadoVal, clasificaVal, partido, options = {}) {
  const { statusRes, statusCls, isPrediction } = options;
  const resClass = isPrediction && statusRes
    ? ` mcard__compare-val--${statusRes}`
    : " mcard__compare-val--real";
  const clsWrapClass = isPrediction && statusCls
    ? `mcard__compare-cls mcard__compare-cls--${statusCls}`
    : "mcard__compare-cls mcard__compare-cls--real";
  return `
    <div class="mcard__compare-picks">
      <span class="mcard__compare-val${resClass}">${formatPickValue(resultadoVal)}</span>
      <span class="${clsWrapClass}">${formatClasificaFlagHtml(clasificaVal, partido)}</span>
    </div>
  `;
}

function formatFinishedCompareHtml(pronostico, resultado, partido) {
  const p = normalizePick(pronostico, partido.fase);
  const r = normalizeResultado(resultado, partido.fase);
  const pts = calcPuntosPartido(pronostico, resultado, partido);
  const dual = isEliminatoriaFase(partido.fase);

  if (!dual) {
    const status = betFieldStatus(p.resultado, r.resultado);
    return `
      <div class="mcard__compare mcard__compare--single">
        <div class="mcard__compare-col">
          <span class="mcard__compare-k">Quedó</span>
          <span class="mcard__compare-val mcard__compare-val--real mcard__compare-val--lg">${formatPickValue(r.resultado)}</span>
        </div>
        <div class="mcard__compare-col">
          <span class="mcard__compare-k">Apostaste</span>
          <span class="mcard__compare-val mcard__compare-val--${status} mcard__compare-val--lg">${formatPickValue(p.resultado)}</span>
        </div>
      </div>
      ${formatPointsBadge(pts)}
    `;
  }

  const statusRes = betFieldStatus(p.resultado, r.resultado);
  const statusCls = betFieldStatus(p.clasifica, r.clasifica);

  return `
    <div class="mcard__compare mcard__compare--dual">
      <div class="mcard__compare-col">
        <span class="mcard__compare-k">Quedó</span>
        ${formatComparePickRow(r.resultado, r.clasifica, partido, {})}
      </div>
      <div class="mcard__compare-col">
        <span class="mcard__compare-k">Apostaste</span>
        ${formatComparePickRow(p.resultado, p.clasifica, partido, {
          statusRes,
          statusCls,
          isPrediction: true,
        })}
      </div>
    </div>
    ${formatPointsBadge(pts)}
  `;
}

function createMatchCard(partido, pronostico, resultado, marcador, index) {
  const status = getMatchStatus(pronostico, resultado, partido.fase);
  const isFinished = status !== "pending";
  const dual = isEliminatoriaFase(partido.fase);

  if (!isFinished && dual) {
    const row = createNextMatchRow(partido, pronostico, index);
    row.classList.add("next-row--phase");
    return row;
  }

  const hasScore = isFinished && marcador && marcador.home != null && marcador.away != null;

  const card = document.createElement("div");
  card.className = `mcard mcard--${status}${dual ? " mcard--dual" : ""}`;
  card.style.animationDelay = `${0.04 * index}s`;

  if (isFinished) {
    const scoreDisplay = hasScore ? `${marcador.home}-${marcador.away}` : "vs";
    const verdictHtml = formatFinishedCompareHtml(pronostico, resultado, partido);
    card.innerHTML = `
      ${formatWhenSpainHtml(partido, "mcard")}
      <div class="mcard__scoreline">
        <div class="mcard__team mcard__team--home">
          ${flagImg(partido.local, "flag flag--sm")}
          <span class="mcard__team-name">${partido.local}</span>
        </div>
        <div class="mcard__score${hasScore ? "" : " mcard__score--vs"}">${scoreDisplay}</div>
        <div class="mcard__team mcard__team--away">
          <span class="mcard__team-name">${partido.visitante}</span>
          ${flagImg(partido.visitante, "flag flag--sm")}
        </div>
      </div>
      <div class="mcard__verdict mcard__verdict--finished">${verdictHtml}</div>
    `;
  } else {
    card.innerHTML = `
      ${formatWhenSpainHtml(partido, "mcard")}
      <div class="mcard__matchup">
        ${flagImg(partido.local, "flag flag--sm")}
        <span class="mcard__matchup-teams">${partido.local} <span class="mcard__vs">vs</span> ${partido.visitante}</span>
        ${flagImg(partido.visitante, "flag flag--sm")}
      </div>
      <div class="mcard__pick-big">${formatPickValue(normalizePick(pronostico, partido.fase).resultado)}</div>
    `;
  }

  return card;
}

function buildGroupStats(matchesToRender, pronosticos, resultados) {
  return matchesToRender.reduce((acc, { index, partido }) => {
    const stats = scoreMatchBets(
      pronosticos[index],
      resultados[index],
      partido?.fase || "grupos",
    );
    acc.hits += stats.hits;
    acc.misses += stats.misses;
    acc.pending += stats.pending;
    return acc;
  }, { hits: 0, misses: 0, pending: 0 });
}

function renderMatchList() {
  const { participante } = detailState;
  if (!participante) return;

  const partidos = appData.partidos || [];
  const resultados = appData.resultados || [];
  const marcadores = appData.marcadores || [];
  const pronosticos = participante.pronosticos;
  const groups = buildGroupsMap();

  elements.predList.innerHTML = "";

  if (detailState.activeTab === "proximos") {
    const pending = [];
    partidos.forEach((p, i) => {
      if (!isProximosPartido(p, i, resultados)) return;
      pending.push({ partido: p, index: i });
    });
    pending.sort((a, b) => {
      const da = new Date(`${a.partido.fecha}T${a.partido.hora}:00`);
      const db = new Date(`${b.partido.fecha}T${b.partido.hora}:00`);
      return da - db;
    });

    if (pending.length === 0) {
      elements.predList.innerHTML = `
        <div class="pred-error">
          <span aria-hidden="true">🏆</span>
          <p>No quedan partidos de ${FASE_LABELS[PROXIMOS_FASE].toLowerCase()} por jugar.</p>
        </div>
      `;
      return;
    }

    const header = document.createElement("div");
    header.className = "match-list__header";
    header.innerHTML = `
      <h3 class="match-list__title">${FASE_LABELS[PROXIMOS_FASE]}</h3>
      <span class="match-list__meta">${pending.length} por jugar</span>
    `;
    elements.predList.appendChild(header);

    pending.forEach(({ partido, index }, i) => {
      elements.predList.appendChild(createNextMatchRow(partido, pronosticos[index] ?? null, i));
    });
    return;
  }

  let matchesToRender = [];
  if (detailState.activeTab === "grupos") {
    const groupIdx = detailState.activeGroup;
    partidos.forEach((p, i) => {
      if (p.fase !== "grupos") return;
      if (getGroupForMatch(p, groups) !== groupIdx) return;
      matchesToRender.push({ partido: p, index: i });
    });
  } else {
    partidos.forEach((p, i) => {
      if (p.fase === detailState.activeTab) matchesToRender.push({ partido: p, index: i });
    });
  }

  if (matchesToRender.length === 0) {
    elements.predList.innerHTML = `<div class="pred-error"><p>No hay partidos en esta fase.</p></div>`;
    return;
  }

  matchesToRender = sortMatchesBySchedule(matchesToRender);

  const stats = buildGroupStats(matchesToRender, pronosticos, resultados);
  const played = stats.hits + stats.misses;
  const pct = played > 0 ? Math.round((stats.hits / played) * 100) : null;

  const label = detailState.activeTab === "grupos"
    ? getGroupLabel(detailState.activeGroup)
    : FASE_LABELS[detailState.activeTab] || detailState.activeTab;

  const teamsMeta = detailState.activeTab === "grupos"
    ? getGroupTeamsLabel(detailState.activeGroup)
    : "";

  const header = document.createElement("div");
  header.className = "gsh";
  header.innerHTML = `
    <div class="gsh__top">
      <h3 class="gsh__name">${label}</h3>
      ${teamsMeta ? `<p class="gsh__teams">${teamsMeta}</p>` : ""}
    </div>
    <div class="gsh__chips">
      ${played > 0 ? `<span class="gsh__chip">${played} jugado${played !== 1 ? "s" : ""}</span>` : ""}
      ${stats.pending > 0 ? `<span class="gsh__chip">${stats.pending} pendiente${stats.pending !== 1 ? "s" : ""}</span>` : ""}
      ${pct !== null ? `<span class="gsh__chip gsh__chip--pct">${pct}% precisión</span>` : ""}
    </div>
  `;
  elements.predList.appendChild(header);

  const grid = document.createElement("div");
  grid.className = isEliminatoriaFase(detailState.activeTab)
    ? "knockout-list"
    : "mcard-grid";
  matchesToRender.forEach(({ partido, index }, i) => {
    grid.appendChild(
      createMatchCard(partido, pronosticos[index] ?? null, resultados[index] ?? null, marcadores[index] ?? null, i)
    );
  });
  elements.predList.appendChild(grid);
}

function renderParticipantDetail(entry, participante) {
  const resultados = appData.resultados || [];
  const partidos = appData.partidos || [];
  const pronosticos = participante.pronosticos;
  const groups = buildGroupsMap();

  detailState = { entry, participante, activeTab: "proximos", activeGroup: 0 };

  renderParticipantDetailHeader(entry);
  renderGroupNav(groups, pronosticos, resultados, partidos);
  renderMatchList();
}

function renderApp(data) {
  renderStats(data, appData.status);
  renderProgress();
  renderPodium(data);
  renderEvolucion();
  renderPremios(appData.premios);
  renderTable(data);
}

/* ── UI state ── */

function showLoading() {
  elements.loading.classList.remove("is-hidden");
  hideError();
}

function hideLoading() {
  elements.loading.classList.add("is-hidden");
}

function showError(message) {
  elements.errorMessage.textContent = message;
  elements.error.classList.add("is-visible");
  hideLoading();
}

function hideError() {
  elements.error.classList.remove("is-visible");
}

/* ── Init ── */

async function init() {
  initAnalytics();
  hideError();
  showLoading();
  try {
    const [clasificacion, premios, partidos, resultados, marcadores, participantes, evolucion, status] = await Promise.all([
      loadClasificacion(),
      loadPremios(),
      loadPartidos().catch(() => null),
      loadResultados().catch(() => null),
      loadMarcadores().catch(() => null),
      loadParticipantes().catch(() => null),
      loadEvolucion().catch(() => null),
      loadStatus(),
    ]);
    appData.clasificacion = clasificacion;
    appData.premios = premios;
    appData.partidos = partidos;
    appData.resultados = resultados;
    appData.marcadores = marcadores;
    appData.participantes = participantes;
    appData.evolucion = evolucion;
    appData.status = status;
    renderApp(clasificacion);
    hideError();
    hideLoading();
  } catch (error) {
    showError(error instanceof Error ? error.message : "Error desconocido al cargar los datos.");
  }
}

if (elements.retryButton) {
  elements.retryButton.addEventListener("click", init);
}
if (elements.closeErrorButton) {
  elements.closeErrorButton.addEventListener("click", hideError);
}
if (elements.btnBack) {
  elements.btnBack.addEventListener("click", () => showView("home"));
}

init();

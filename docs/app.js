const BUILD = document.querySelector('meta[name="app-build"]')?.content || String(Date.now());
const DATA_URL = `./clasificacion.json?v=${BUILD}`;
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
  partidos: null,
  resultados: null,
  marcadores: null,
  participantes: null,
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

const FASE_BADGE_CLASS = {
  grupos: "fase-badge--grupos",
  dieciseisavos: "fase-badge--dieciseisavos",
  octavos: "fase-badge--octavos",
  cuartos: "fase-badge--cuartos",
  semifinales: "fase-badge--semifinales",
  tercer_puesto: "fase-badge--tercer_puesto",
  final: "fase-badge--final",
};

const elements = {
  loading: document.getElementById("loading"),
  error: document.getElementById("error"),
  errorMessage: document.getElementById("error-message"),
  retryButton: document.getElementById("retry-button"),
  closeErrorButton: document.getElementById("close-error-button"),
  stats: document.getElementById("stats"),
  podiumSection: document.getElementById("podium-section"),
  podium: document.getElementById("podium"),
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
  1: "1 (Local)",
  X: "X (Empate)",
  2: "2 (Visitante)",
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

/* ── Match status helpers ── */

function getMatchStatus(pronostico, resultado) {
  if (resultado === null || resultado === undefined) {
    return "pending";
  }
  if (pronostico === resultado) {
    return "hit";
  }
  return "miss";
}

function countPlayedMatches(resultados) {
  return resultados.filter((r) => r !== null && r !== undefined).length;
}

function calcPrecision(aciertos, resultados) {
  const jugados = countPlayedMatches(resultados);
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

function renderStats(data, status) {
  const leader = data[0];
  const partidosCount = appData.partidos ? appData.partidos.length : "—";
  const lastSync = status?.lastWorkflowRun || null;
  const syncOk = Boolean(lastSync && status?.workflowStatus === "ok");
  const stats = {
    participantes: data.length,
    partidos: partidosCount,
    lider: leader ? leader.nombre : "—",
    maxpuntos: PUNTOS_MAXIMOS,
    actualizacion: lastSync ? formatSyncDate(lastSync) : "—",
    "actualizacion-relativa": lastSync ? formatRelativeTime(lastSync) : "—",
  };

  elements.stats.querySelectorAll("[data-stat]").forEach((node) => {
    const key = node.dataset.stat;
    if (key === "error-sincronizacion") return;
    if (stats[key] !== undefined) {
      node.textContent = stats[key];
    }
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

function buildGroupsMap(partidos) {
  const adj = {};
  partidos.forEach((p) => {
    if (p.fase !== "grupos") return;
    adj[p.local] = adj[p.local] || new Set();
    adj[p.visitante] = adj[p.visitante] || new Set();
    adj[p.local].add(p.visitante);
    adj[p.visitante].add(p.local);
  });
  const visited = new Set();
  const groups = [];
  Object.keys(adj).sort().forEach((team) => {
    if (visited.has(team)) return;
    const group = new Set();
    const queue = [team];
    while (queue.length) {
      const t = queue.shift();
      if (visited.has(t)) continue;
      visited.add(t);
      group.add(t);
      (adj[t] || []).forEach((n) => { if (!visited.has(n)) queue.push(n); });
    }
    groups.push([...group].sort());
  });
  groups.sort((a, b) => a[0].localeCompare(b[0]));
  return groups;
}

function getGroupLabel(idx) {
  return `Grupo ${String.fromCharCode(65 + idx)}`;
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
  groupMatches.forEach(({ index }) => {
    const r = resultados[index];
    if (r === null || r === undefined) { pending++; return; }
    if (pronosticos[index] === r) hits++;
    else misses++;
  });
  return { hits, misses, pending, total: groupMatches.length };
}

const PICK_INFO = {
  "1": { label: "Local", short: "1·L" },
  "X": { label: "Empate", short: "X·E" },
  "2": { label: "Visit.", short: "2·V" },
};

function formatMatchDateShort(fecha) {
  const [, m, d] = fecha.split("-");
  const months = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  return `${parseInt(d)} ${months[parseInt(m, 10) - 1]}`;
}

let detailState = { entry: null, participante: null, activeTab: "proximos", activeGroup: 0 };

function renderParticipantDetailHeader(entry) {
  const resultados = appData.resultados || [];
  const pct = calcPrecision(entry.aciertos, resultados);
  const jugados = countPlayedMatches(resultados);
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
  const pendingCount = resultados.filter((r) => r === null || r === undefined).length;

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
      <button class="group-pill${isActive ? " group-pill--active" : ""}" data-group="${i}">
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
  row.className = "next-row";
  row.style.animationDelay = `${0.04 * index}s`;

  row.innerHTML = `
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
    <div class="next-row__when">
      <span class="next-row__date">${formatMatchDateShort(partido.fecha)}</span>
      <span class="next-row__time">${partido.hora}</span>
    </div>
    <div class="next-row__pick-num">${pronostico || "—"}</div>
  `;

  return row;
}

function createMatchCard(partido, pronostico, resultado, marcador, index) {
  const status = getMatchStatus(pronostico, resultado);
  const isFinished = status !== "pending";
  const hasScore = isFinished && marcador && marcador.home != null && marcador.away != null;

  const card = document.createElement("div");
  card.className = `mcard mcard--${status}`;
  card.style.animationDelay = `${0.04 * index}s`;

  if (isFinished) {
    const scoreDisplay = hasScore ? `${marcador.home} - ${marcador.away}` : "— - —";
    const stateIcon = status === "hit" ? "✅" : "❌";
    const stateLabel = status === "hit" ? "Acierto" : "Error";
    card.innerHTML = `
      <div class="mcard__scoreline">
        <div class="mcard__team mcard__team--home">
          ${flagImg(partido.local, "flag flag--sm")}
          <span class="mcard__team-name">${partido.local}</span>
        </div>
        <div class="mcard__score">${scoreDisplay}</div>
        <div class="mcard__team mcard__team--away">
          <span class="mcard__team-name">${partido.visitante}</span>
          ${flagImg(partido.visitante, "flag flag--sm")}
        </div>
      </div>
      <div class="mcard__verdict">
        <span class="mcard__pick">${pronostico || "—"}</span>
        <span class="mcard__state">${stateIcon} ${stateLabel}</span>
      </div>
    `;
  } else {
    const [, m, d] = partido.fecha.split("-");
    const months = ["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"];
    const whenStr = `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]} · ${partido.hora}`;
    card.innerHTML = `
      <div class="mcard__matchup">
        ${flagImg(partido.local, "flag flag--sm")}
        <span class="mcard__matchup-teams">${partido.local} <span class="mcard__vs">vs</span> ${partido.visitante}</span>
        ${flagImg(partido.visitante, "flag flag--sm")}
      </div>
      <div class="mcard__when">${whenStr}</div>
      <div class="mcard__pick-big">${pronostico || "—"}</div>
    `;
  }

  return card;
}

function buildGroupStats(matchesToRender, pronosticos, resultados) {
  return matchesToRender.reduce((acc, { index }) => {
    const r = resultados[index];
    if (r == null) acc.pending++;
    else if (pronosticos[index] === r) acc.hits++;
    else acc.misses++;
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
  const groups = buildGroupsMap(partidos);

  elements.predList.innerHTML = "";

  if (detailState.activeTab === "proximos") {
    const pending = [];
    partidos.forEach((p, i) => {
      if (resultados[i] === null || resultados[i] === undefined) {
        pending.push({ partido: p, index: i });
      }
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
          <p>¡Todos los partidos han sido disputados!</p>
        </div>
      `;
      return;
    }

    const header = document.createElement("div");
    header.className = "match-list__header";
    header.innerHTML = `
      <h3 class="match-list__title">Próximos partidos</h3>
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

  const stats = buildGroupStats(matchesToRender, pronosticos, resultados);
  const played = stats.hits + stats.misses;
  const pct = played > 0 ? Math.round((stats.hits / played) * 100) : null;

  const label = detailState.activeTab === "grupos"
    ? getGroupLabel(detailState.activeGroup)
    : FASE_LABELS[detailState.activeTab] || detailState.activeTab;

  const header = document.createElement("div");
  header.className = "gsh";
  header.innerHTML = `
    <div class="gsh__top">
      <h3 class="gsh__name">${label}</h3>
      <div class="gsh__ratio">${stats.hits}/${matchesToRender.length} <span class="gsh__ratio-label">aciertos</span></div>
    </div>
    <div class="gsh__chips">
      ${played > 0 ? `<span class="gsh__chip">${played} jugado${played !== 1 ? "s" : ""}</span>` : ""}
      ${stats.pending > 0 ? `<span class="gsh__chip">${stats.pending} pendiente${stats.pending !== 1 ? "s" : ""}</span>` : ""}
      ${pct !== null ? `<span class="gsh__chip gsh__chip--pct">${pct}% precisión</span>` : ""}
    </div>
  `;
  elements.predList.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "mcard-grid";
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
  const groups = buildGroupsMap(partidos);

  detailState = { entry, participante, activeTab: "proximos", activeGroup: 0 };

  renderParticipantDetailHeader(entry);
  renderGroupNav(groups, pronosticos, resultados, partidos);
  renderMatchList();
}

function renderApp(data) {
  renderStats(data, appData.status);
  renderPodium(data);
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
  hideError();
  showLoading();
  try {
    const [clasificacion, partidos, resultados, marcadores, participantes, status] = await Promise.all([
      loadClasificacion(),
      loadPartidos().catch(() => null),
      loadResultados().catch(() => null),
      loadMarcadores().catch(() => null),
      loadParticipantes().catch(() => null),
      loadStatus(),
    ]);
    appData.clasificacion = clasificacion;
    appData.partidos = partidos;
    appData.resultados = resultados;
    appData.marcadores = marcadores;
    appData.participantes = participantes;
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

const BUILD = document.querySelector('meta[name="app-build"]')?.content || String(Date.now());
const DATA_URL = `./clasificacion.json?v=${BUILD}`;
const PARTIDOS_URL = `./partidos.json?v=${BUILD}`;
const PUNTOS_MAXIMOS = 275;

const appData = {
  clasificacion: null,
  partidos: null,
};

const MEDALS = { 1: "🥇", 2: "🥈", 3: "🥉" };
const PODIUM_ORDER = [2, 1, 3];

const FASES = [
  { key: "grupos", label: "Grupos", max: 72 },
  { key: "dieciseisavos", label: "Dieciseisavos", max: 16 },
  { key: "octavos", label: "Octavos", max: 8 },
  { key: "cuartos", label: "Cuartos", max: 4 },
  { key: "semifinales", label: "Semifinales", max: 2 },
  { key: "tercer_puesto", label: "3er puesto", max: 1 },
  { key: "final", label: "Final", max: 1 },
];

const FASE_LABELS = {
  grupos: "Grupos",
  dieciseisavos: "Dieciseisavos",
  octavos: "Octavos",
  cuartos: "Cuartos",
  semifinales: "Semifinales",
  tercer_puesto: "3er puesto",
  final: "Final",
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
  matchesSection: document.getElementById("matches-section"),
  matchesList: document.getElementById("matches-list"),
  viewHome: document.getElementById("view-home"),
  viewParticipant: document.getElementById("view-participant"),
  btnBack: document.getElementById("btn-back"),
  detailHero: document.getElementById("detail-hero"),
  detailStats: document.getElementById("detail-stats"),
  phaseGrid: document.getElementById("phase-grid"),
  perfGrid: document.getElementById("perf-grid"),
};

/* ── Data loading (sin cambios) ── */

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

function formatDate(date) {
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatMatchDate(iso) {
  const [y, m, d] = iso.split("-");
  return new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short" }).format(
    new Date(y, m - 1, d)
  );
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
    } catch { continue; }
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

/* ── Navigation ── */

function showView(view) {
  elements.viewHome.classList.remove("view--active");
  elements.viewParticipant.classList.remove("view--active");
  elements.viewParticipant.hidden = true;
  if (view === "participant") {
    elements.viewParticipant.hidden = false;
    elements.viewParticipant.classList.add("view--active");
  } else {
    elements.viewHome.classList.add("view--active");
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openParticipant(nombre) {
  const entry = appData.clasificacion.find((e) => e.nombre === nombre);
  if (!entry) return;
  renderParticipantDetail(entry);
  showView("participant");
}

/* ── Rendering ── */

function renderStats(data, updatedAt) {
  const leader = data[0];
  const partidosCount = appData.partidos ? appData.partidos.length : "—";
  const stats = {
    participantes: data.length,
    partidos: partidosCount,
    lider: leader ? leader.nombre : "—",
    maxpuntos: PUNTOS_MAXIMOS,
    actualizacion: formatDate(updatedAt),
  };
  elements.stats.querySelectorAll("[data-stat]").forEach((node) => {
    node.textContent = stats[node.dataset.stat];
  });
}

function createPodiumPlayer(entry) {
  const pos = entry.posicion;
  const article = document.createElement("article");
  article.className = `podium-player podium-player--${pos}`;
  article.setAttribute("role", "listitem");

  article.innerHTML = `
    <span class="podium-player__medal" aria-hidden="true">${getMedal(pos)}</span>
    <div class="podium-player__avatar" data-player="${entry.nombre}">${getInitials(entry.nombre)}</div>
    <h3 class="podium-player__name" data-player="${entry.nombre}">${entry.nombre}</h3>
    <span class="podium-player__points">${entry.puntos}</span>
    <span class="podium-player__meta">${entry.aciertos} aciertos</span>
    <div class="podium-player__stand">
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
  const isTop = entry.posicion <= 3;
  if (isTop) row.classList.add("row--top");
  row.style.animationDelay = `${0.04 * index}s`;

  row.innerHTML = `
    <td class="col-pos">${formatPosition(entry.posicion)}</td>
    <td class="col-avatar"><div class="player-avatar">${getInitials(entry.nombre)}</div></td>
    <td class="col-name">${entry.nombre}</td>
    <td class="num">${entry.aciertos}</td>
    <td class="num col-points">${entry.puntos}</td>
    <td><span class="trend-icon" title="Próximamente">—</span></td>
  `;

  row.addEventListener("click", () => openParticipant(entry.nombre));
  return row;
}

function createMobileRow(entry, index) {
  const row = document.createElement("article");
  const isTop = entry.posicion <= 3;
  row.className = `mobile-row${isTop ? " mobile-row--top" : ""}`;
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

function createMatchCard(partido, index) {
  const card = document.createElement("article");
  card.className = "match-card";
  card.setAttribute("role", "listitem");
  card.style.animationDelay = `${0.02 * index}s`;

  card.innerHTML = `
    <div class="match-card__meta">
      <span class="match-card__date">${formatMatchDate(partido.fecha)}</span>
      <span class="match-card__time">${partido.hora}</span>
      <span class="match-card__phase">${FASE_LABELS[partido.fase] || partido.fase}</span>
    </div>
    <div class="match-card__teams">
      <div class="match-card__team">${flagImg(partido.local)} ${partido.local}</div>
      <span class="match-card__vs">VS</span>
      <div class="match-card__team">${flagImg(partido.visitante)} ${partido.visitante}</div>
    </div>
    <div class="match-card__slots">
      <span class="match-card__slot">Resultado</span>
      <span class="match-card__slot">Pronóstico</span>
    </div>
  `;
  return card;
}

function renderMatches(partidos) {
  if (!partidos || partidos.length === 0) {
    elements.matchesSection.hidden = true;
    return;
  }
  elements.matchesSection.hidden = false;
  elements.matchesList.innerHTML = "";
  partidos.forEach((p, i) => elements.matchesList.appendChild(createMatchCard(p, i)));
}

function countPartidosByFase(partidos) {
  const counts = {};
  if (!partidos) return counts;
  partidos.forEach((p) => {
    counts[p.fase] = (counts[p.fase] || 0) + 1;
  });
  return counts;
}

function renderParticipantDetail(entry) {
  const pct = appData.partidos
    ? Math.round((entry.aciertos / appData.partidos.length) * 100)
    : 0;
  const faseCounts = countPartidosByFase(appData.partidos);

  elements.detailHero.innerHTML = `
    <div class="detail-hero__avatar">${getInitials(entry.nombre)}</div>
    <h1 class="detail-hero__name">${entry.nombre}</h1>
    <p class="detail-hero__rank">${formatPosition(entry.posicion)} en la clasificación</p>
  `;

  elements.detailStats.innerHTML = `
    <div class="detail-stat">
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
    </div>
    <div class="detail-stat">
      <div class="detail-stat__value">${entry.posicion}º</div>
      <div class="detail-stat__label">Posición</div>
    </div>
  `;

  elements.phaseGrid.innerHTML = FASES.map((fase) => {
    const count = faseCounts[fase.key] || 0;
    const active = count > 0;
    return `
      <div class="phase-card">
        <div class="phase-card__name">${fase.label}</div>
        <div class="phase-card__value${active ? " phase-card__value--active" : ""}">—</div>
        <div class="phase-card__sub">${count > 0 ? `${count} partidos` : "Próximamente"}</div>
      </div>
    `;
  }).join("");

  elements.perfGrid.innerHTML = `
    <div class="perf-card">
      <div class="perf-card__label">Mejor fase</div>
      <div class="perf-card__value">Próximamente</div>
    </div>
    <div class="perf-card">
      <div class="perf-card__label">Peor fase</div>
      <div class="perf-card__value">Próximamente</div>
    </div>
    <div class="perf-card">
      <div class="perf-card__label">Precisión global</div>
      <div class="perf-card__value">${pct}%</div>
    </div>
  `;
}

function renderApp(data) {
  const updatedAt = new Date();
  renderStats(data, updatedAt);
  renderPodium(data);
  renderTable(data);
  renderMatches(appData.partidos);
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
    const [clasificacion, partidos] = await Promise.all([
      loadClasificacion(),
      loadPartidos().catch(() => null),
    ]);
    appData.clasificacion = clasificacion;
    appData.partidos = partidos;
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

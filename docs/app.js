const BUILD = document.querySelector('meta[name="app-build"]')?.content || String(Date.now());
const DATA_URL = `./clasificacion.json?v=${BUILD}`;
const PARTIDOS_URL = `./partidos.json?v=${BUILD}`;
const RESULTADOS_URL = `./resultados.json?v=${BUILD}`;
const PARTICIPANTES_URL = `./participantes.json?v=${BUILD}`;
const PUNTOS_MAXIMOS = 275;

const appData = {
  clasificacion: null,
  partidos: null,
  resultados: null,
  participantes: null,
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

function formatDate(date) {
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatMatchDateTime(fecha, hora) {
  const [y, m, d] = fecha.split("-");
  return `${d}/${m}/${y} · ${hora}`;
}

function formatResultado(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
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
    <td><span class="trend-icon" title="Ver detalle">→</span></td>
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

/* ── Rendering: participant detail ── */

function renderParticipantDetailHeader(entry, precision) {
  const pct = precision ?? calcPrecision(entry.aciertos, appData.resultados || []);
  const jugados = countPlayedMatches(appData.resultados || []);

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
      <div class="detail-stat__sub">${entry.aciertos} de ${jugados} jugados</div>
    </div>
    <div class="detail-stat">
      <div class="detail-stat__value">${entry.posicion}º</div>
      <div class="detail-stat__label">Posición</div>
    </div>
  `;
}

function createStatusBadge(status) {
  const badges = {
    hit: { className: "pred-status--hit", icon: "✅", label: "Acierto" },
    miss: { className: "pred-status--miss", icon: "❌", label: "Error" },
    pending: { className: "pred-status--pending", icon: "⏳", label: "Pendiente" },
  };
  const badge = badges[status];
  return `<span class="pred-status ${badge.className}">${badge.icon} ${badge.label}</span>`;
}

function createPredCard(partido, pronostico, resultado, index) {
  const status = getMatchStatus(pronostico, resultado);
  const card = document.createElement("article");
  card.className = `pred-card pred-card--${status}`;
  card.setAttribute("role", "listitem");
  card.style.animationDelay = `${0.02 * index}s`;

  const faseLabel = FASE_LABELS[partido.fase] || partido.fase;
  const faseClass = FASE_BADGE_CLASS[partido.fase] || "fase-badge--grupos";
  const resultadoTexto =
    resultado === null || resultado === undefined ? "Pendiente" : formatResultado(resultado);

  card.innerHTML = `
    <div class="pred-card__header">
      <div class="pred-card__datetime">${formatMatchDateTime(partido.fecha, partido.hora)}</div>
      <span class="fase-badge ${faseClass}">${faseLabel}</span>
    </div>
    <div class="pred-card__matchup">
      <div class="pred-card__team">${flagImg(partido.local)} <span>${partido.local}</span></div>
      <span class="pred-card__vs">vs</span>
      <div class="pred-card__team">${flagImg(partido.visitante)} <span>${partido.visitante}</span></div>
    </div>
    <div class="pred-card__results">
      <div class="pred-card__field">
        <span class="pred-card__field-label">Pronóstico</span>
        <span class="pred-card__field-value pred-card__field-value--pick">${formatResultado(pronostico)}</span>
      </div>
      <div class="pred-card__field">
        <span class="pred-card__field-label">Resultado</span>
        <span class="pred-card__field-value${status === "pending" ? " pred-card__field-value--pending" : ""}">${resultadoTexto}</span>
      </div>
      <div class="pred-card__field pred-card__field--status">
        <span class="pred-card__field-label">Estado</span>
        ${createStatusBadge(status)}
      </div>
    </div>
  `;

  return card;
}

function renderParticipantDetail(entry, participante) {
  const resultados = appData.resultados || [];
  const partidos = appData.partidos || [];
  const precision = calcPrecision(entry.aciertos, resultados);

  renderParticipantDetailHeader(entry, precision);

  elements.predList.innerHTML = "";

  if (partidos.length === 0) {
    elements.predList.innerHTML = `
      <div class="pred-error">
        <p>No hay partidos disponibles en partidos.json.</p>
      </div>
    `;
    return;
  }

  partidos.forEach((partido, index) => {
    const pronostico = participante.pronosticos[index] ?? null;
    const resultado = resultados[index] ?? null;
    elements.predList.appendChild(createPredCard(partido, pronostico, resultado, index));
  });
}

function renderApp(data) {
  const updatedAt = new Date();
  renderStats(data, updatedAt);
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
    const [clasificacion, partidos, resultados, participantes] = await Promise.all([
      loadClasificacion(),
      loadPartidos().catch(() => null),
      loadResultados().catch(() => null),
      loadParticipantes().catch(() => null),
    ]);
    appData.clasificacion = clasificacion;
    appData.partidos = partidos;
    appData.resultados = resultados;
    appData.participantes = participantes;
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

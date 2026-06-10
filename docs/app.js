const DATA_URL = "./clasificacion.json";
const PARTIDOS_URL = "./partidos.json";

const appData = {
  clasificacion: null,
  partidos: null,
};

const MEDALS = {
  1: "🥇",
  2: "🥈",
  3: "🥉",
};

const PODIUM_ORDER = [2, 1, 3];
const PODIUM_CLASSES = {
  1: "podium-card--first",
  2: "podium-card--second",
  3: "podium-card--third",
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
};

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
  if (!node || !node.textContent.trim()) {
    return null;
  }
  const data = JSON.parse(node.textContent);
  validateData(data);
  return data;
}

function loadEmbeddedClasificacion() {
  if (!window.__CLASIFICACION__) {
    return null;
  }
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
  const sources = [loadInlineClasificacion, loadEmbeddedClasificacion];

  for (const source of sources) {
    try {
      const data = source();
      if (data) {
        return data;
      }
    } catch {
      continue;
    }
  }

  return null;
}

async function loadClasificacion() {
  const localData = loadClasificacionSync();
  if (localData) {
    return localData;
  }

  const canFetch = window.location.protocol === "http:"
    || window.location.protocol === "https:";

  if (canFetch) {
    return fetchClasificacion();
  }

  throw new Error(
    "No se encontraron datos. Ejecuta calcular_clasificacion.py para actualizar la clasificación."
  );
}

function loadEmbeddedPartidos() {
  if (!window.__PARTIDOS__) {
    return null;
  }
  return window.__PARTIDOS__;
}

async function fetchPartidos() {
  const response = await fetch(PARTIDOS_URL);
  if (!response.ok) {
    throw new Error(`No se pudo acceder a partidos.json (${response.status}).`);
  }
  return response.json();
}

async function loadPartidos() {
  const embedded = loadEmbeddedPartidos();
  if (embedded) {
    return embedded;
  }

  const canFetch = window.location.protocol === "http:"
    || window.location.protocol === "https:";

  if (canFetch) {
    return fetchPartidos();
  }

  return null;
}

function renderStats(data, updatedAt) {
  const leader = data[0];
  const stats = {
    participantes: data.length,
    lider: leader ? leader.nombre : "—",
    actualizacion: formatDate(updatedAt),
  };

  elements.stats.querySelectorAll("[data-stat]").forEach((node) => {
    const key = node.dataset.stat;
    node.textContent = stats[key];
  });
}

function createPodiumCard(entry) {
  const position = entry.posicion;
  const card = document.createElement("article");
  card.className = `podium-card ${PODIUM_CLASSES[position] || ""}`;
  card.setAttribute("role", "listitem");

  card.innerHTML = `
    <span class="podium-card__medal" aria-hidden="true">${getMedal(position)}</span>
    <span class="podium-card__rank">${position}º puesto</span>
    <h3 class="podium-card__name">${entry.nombre}</h3>
    <span class="podium-card__points">${entry.puntos}</span>
    <span class="podium-card__label">puntos</span>
    <span class="podium-card__aciertos">${entry.aciertos} aciertos</span>
  `;

  return card;
}

function renderPodium(data) {
  const topThree = data.filter((entry) => entry.posicion <= 3);
  elements.podium.innerHTML = "";

  if (topThree.length === 0) {
    elements.podiumSection.hidden = true;
    return;
  }

  elements.podiumSection.hidden = false;

  const ordered = PODIUM_ORDER
    .map((pos) => topThree.find((entry) => entry.posicion === pos))
    .filter(Boolean);

  ordered.forEach((entry) => {
    elements.podium.appendChild(createPodiumCard(entry));
  });
}

function createTableRow(entry, index) {
  const row = document.createElement("tr");
  const isTop = entry.posicion <= 3;

  if (isTop) row.classList.add("row--top");
  row.style.animationDelay = `${0.05 * index}s`;

  row.innerHTML = `
    <td class="col-pos">${formatPosition(entry.posicion)}</td>
    <td class="col-player">${entry.nombre}</td>
    <td class="col-num">${entry.aciertos}</td>
    <td class="col-num col-points">${entry.puntos}</td>
  `;

  return row;
}

function createMobileCard(entry, index) {
  const card = document.createElement("article");
  const isTop = entry.posicion <= 3;

  card.className = `mobile-card${isTop ? " mobile-card--top" : ""}`;
  card.setAttribute("role", "listitem");
  card.style.animationDelay = `${0.05 * index}s`;

  card.innerHTML = `
    <div class="mobile-card__pos">${formatPosition(entry.posicion)}</div>
    <div class="mobile-card__info">
      <div class="mobile-card__name">${entry.nombre}</div>
      <div class="mobile-card__meta">${entry.aciertos} aciertos</div>
    </div>
    <div class="mobile-card__points">${entry.puntos}</div>
  `;

  return card;
}

function renderTable(data) {
  elements.leaderboardBody.innerHTML = "";
  elements.mobileCards.innerHTML = "";

  data.forEach((entry, index) => {
    elements.leaderboardBody.appendChild(createTableRow(entry, index));
    elements.mobileCards.appendChild(createMobileCard(entry, index));
  });
}

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

function renderApp(data) {
  const updatedAt = new Date();
  renderStats(data, updatedAt);
  renderPodium(data);
  renderTable(data);
}

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
    const message = error instanceof Error
      ? error.message
      : "Error desconocido al cargar los datos.";
    showError(message);
  }
}

if (elements.retryButton) {
  elements.retryButton.addEventListener("click", init);
}

if (elements.closeErrorButton) {
  elements.closeErrorButton.addEventListener("click", hideError);
}

init();

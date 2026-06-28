/**
 * Carga condicional de plataformas de analítica.
 * Ampliar aquí si se añaden más proveedores en el futuro.
 */

const CLOUDFLARE_BEACON_URL = "https://static.cloudflareinsights.com/beacon.min.js";
const CLOUDFLARE_TOKEN_PLACEHOLDER = "YOUR_CLOUDFLARE_ANALYTICS_TOKEN";

/**
 * Inserta el beacon de Cloudflare Web Analytics en <head>.
 * No hace nada si el token no está configurado o ya se cargó.
 */
function initCloudflareWebAnalytics(token) {
  const normalizedToken = String(token || "").trim();
  if (!normalizedToken || normalizedToken === CLOUDFLARE_TOKEN_PLACEHOLDER) {
    return;
  }

  if (document.querySelector(`script[src="${CLOUDFLARE_BEACON_URL}"]`)) {
    return;
  }

  const script = document.createElement("script");
  script.defer = true;
  script.src = CLOUDFLARE_BEACON_URL;
  script.setAttribute(
    "data-cf-beacon",
    JSON.stringify({ token: normalizedToken, spa: true })
  );
  document.head.appendChild(script);
}

/**
 * Inicializa la analítica según APP_CONFIG.
 * Si analytics.enabled es false, no modifica el DOM.
 */
function initAnalytics() {
  const analyticsConfig = window.APP_CONFIG?.analytics;
  if (!analyticsConfig?.enabled) {
    return;
  }

  initCloudflareWebAnalytics(analyticsConfig.cloudflareToken);
}

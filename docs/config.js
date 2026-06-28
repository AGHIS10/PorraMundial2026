/**
 * Configuración central del frontend.
 * Único punto para activar servicios externos (analítica, etc.).
 */
window.APP_CONFIG = {
  analytics: {
    /** false = no se inserta ningún script en el DOM */
    enabled: true,
    /** Token de Cloudflare Web Analytics (Dashboard → Web Analytics → Manage site) */
    cloudflareToken: "121554bfa6f847cca0e5fc66f218b332",
  },
};

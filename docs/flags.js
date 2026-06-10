const TEAM_ISO = {
  "Alemania": "de",
  "Arabia Saudí": "sa",
  "Argelia": "dz",
  "Argentina": "ar",
  "Australia": "au",
  "Austria": "at",
  "Bosnia y Herzegovina": "ba",
  "Brasil": "br",
  "Bélgica": "be",
  "Cabo Verde": "cv",
  "Canadá": "ca",
  "Catar": "qa",
  "Colombia": "co",
  "Corea del Sur": "kr",
  "Costa de Marfil": "ci",
  "Croacia": "hr",
  "Curazao": "cw",
  "Ecuador": "ec",
  "Egipto": "eg",
  "Escocia": "gb-sct",
  "España": "es",
  "Estados Unidos": "us",
  "Francia": "fr",
  "Ghana": "gh",
  "Haití": "ht",
  "Inglaterra": "gb-eng",
  "Irak": "iq",
  "Irán": "ir",
  "Japón": "jp",
  "Jordania": "jo",
  "Marruecos": "ma",
  "México": "mx",
  "Noruega": "no",
  "Nueva Zelanda": "nz",
  "Panamá": "pa",
  "Paraguay": "py",
  "Países Bajos": "nl",
  "Portugal": "pt",
  "RD Congo": "cd",
  "República Checa": "cz",
  "Senegal": "sn",
  "Sudáfrica": "za",
  "Suecia": "se",
  "Suiza": "ch",
  "Turquía": "tr",
  "Túnez": "tn",
  "Uruguay": "uy",
  "Uzbekistán": "uz",
};

function getFlagUrl(team, size = 40) {
  const iso = TEAM_ISO[team];
  if (!iso) return null;
  return `https://flagcdn.com/w${size}/${iso}.png`;
}

function flagImg(team, className = "flag") {
  const url = getFlagUrl(team, 40);
  if (!url) {
    return `<span class="flag-fallback" aria-hidden="true">${team.slice(0, 2).toUpperCase()}</span>`;
  }
  return `<img src="${url}" alt="" class="${className}" width="28" height="20" loading="lazy">`;
}

function getInitials(name) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

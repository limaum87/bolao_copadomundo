const countryCodes = {
    'África do Sul': 'za',
    'Alemanha': 'de',
    'Arábia Saudita': 'sa',
    'Argélia': 'dz',
    'Argentina': 'ar',
    'Austrália': 'au',
    'Áustria': 'at',
    'Bélgica': 'be',
    'Bósnia': 'ba',
    'Brasil': 'br',
    'Cabo Verde': 'cv',
    'Canadá': 'ca',
    'Colômbia': 'co',
    'Coreia do Sul': 'kr',
    'Costa do Marfim': 'ci',
    'Croácia': 'hr',
    'Curaçao': 'cw',
    'Egito': 'eg',
    'Equador': 'ec',
    'Escócia': 'gb-sct',
    'Espanha': 'es',
    'Estados Unidos': 'us',
    'França': 'fr',
    'Gana': 'gh',
    'Haiti': 'ht',
    'Holanda': 'nl',
    'Inglaterra': 'gb-eng',
    'Iraque': 'iq',
    'Irã': 'ir',
    'Japão': 'jp',
    'Jordânia': 'jo',
    'Marrocos': 'ma',
    'México': 'mx',
    'Noruega': 'no',
    'Nova Zelândia': 'nz',
    'Panamá': 'pa',
    'Paraguai': 'py',
    'Portugal': 'pt',
    'RD Congo': 'cd',
    'República Tcheca': 'cz',
    'Qatar': 'qa',
    'Catar': 'qa',
    'Senegal': 'sn',
    'Suécia': 'se',
    'Suíça': 'ch',
    'Tunísia': 'tn',
    'Turquia': 'tr',
    'Uruguai': 'uy',
    'Uzbequistão': 'uz'
};

function getFlagUrl(teamName) {
    const code = countryCodes[teamName];
    if (code) {
        return `https://flagcdn.com/w40/${code}.png`;
    }
    return null;
}

function getTeamHtml(teamName) {
    const flagUrl = getFlagUrl(teamName);
    if (flagUrl) {
        return `
            <div class="team-flex">
                <img src="${flagUrl}" alt="${teamName}" class="team-flag">
                <span class="team-name-text">${teamName}</span>
            </div>
        `;
    }
    return `<span class="team-name-text">${teamName}</span>`;
}

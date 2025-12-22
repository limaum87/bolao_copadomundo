const countryCodes = {
    'África do Sul': 'za',
    'Alemanha': 'de',
    'Arábia Saudita': 'sa',
    'Argélia': 'dz',
    'Argentina': 'ar',
    'Austrália': 'au',
    'Áustria': 'at',
    'Bélgica': 'be',
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
    'Qatar': 'qa',
    'Senegal': 'sn',
    'Suíça': 'ch',
    'Tunísia': 'tn',
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

<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- PWA -->
    <meta name="theme-color" content="#009739">
    <meta name="color-scheme" content="light">
    <link rel="manifest" href="/manifest.webmanifest">
    <link rel="icon" href="/assets/img/favicon.ico" sizes="any">
    <link rel="icon" href="/assets/img/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png?v=2">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Bolão Copa">
    <meta name="mobile-web-app-capable" content="yes">
    <script src="/assets/js/pwa-register.js?v=202606141800" defer></script>
    <title>Palpites Finais - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606171200">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
    <style>
        /* Ajustes específicos desta página */
        .finals-cell {
            min-width: 150px;
        }
        .finals-cell .team-flex {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .finals-cell .hit-badge {
            margin-left: 6px;
            font-size: 0.7rem;
        }
        .outcome-banner {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem 1.25rem;
            align-items: center;
        }
        .outcome-item {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
        }
        .outcome-item .pos-label {
            font-weight: 700;
            color: var(--color-gray-600, #555);
            margin-right: 2px;
        }
        .search-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            align-items: center;
        }
        .search-row .form-input {
            max-width: 320px;
        }
        .stats-row {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        .stat-pill {
            background: var(--color-gray-100, #f1f5f9);
            border-radius: 999px;
            padding: 0.35rem 0.85rem;
            font-size: 0.85rem;
            font-weight: 500;
        }
    </style>
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div>
                    <h1>Palpites Finais</h1>
                    <span class="header-subtitle">Palpites de campeão até 4º lugar de todos os participantes</span>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="logout()" class="btn btn-outline btn-sm">🚪 Sair</button>
                    <a href="/" class="btn btn-secondary btn-sm">← Voltar ao Início</a>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
        <div class="container">
            <!-- Admin Navigation -->
            <nav class="admin-nav">
                <a href="/admin/index.php">🏠 Dashboard</a>
                <a href="/admin/participantes.php">👥 Participantes</a>
                <a href="/admin/palpites-finais.php" class="active">🏆 Palpites Finais</a>
                <a href="/admin/jogos.php">⚽ Jogos</a>
                <a href="/admin/configuracoes.php">⚙️ Configurações</a>
            </nav>

            <!-- Resultado oficial -->
            <div class="card mb-lg">
                <div class="card-header">
                    <h3 class="card-title">🏆 Resultado Oficial</h3>
                    <span id="outcomeStatus" class="badge badge-warning">Não definido</span>
                </div>
                <div class="card-body">
                    <div id="outcomeBanner" class="outcome-banner text-muted">
                        Carregando resultado oficial...
                    </div>
                </div>
            </div>

            <!-- Resumo -->
            <div class="stats-row mb-lg">
                <span class="stat-pill" id="statTotal">👥 Participantes: ...</span>
                <span class="stat-pill" id="statComplete">✅ Completos: ...</span>
                <span class="stat-pill" id="statPending">⚠️ Pendentes: ...</span>
            </div>

            <!-- Tabela de palpites -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">📋 Palpites por Participante</h3>
                </div>
                <div class="card-body">
                    <div class="search-row mb-lg">
                        <input type="text" id="searchInput" class="form-input" placeholder="🔎 Buscar participante...">
                        <label class="flex" style="align-items:center; gap:6px; font-size:0.85rem;">
                            <input type="checkbox" id="onlyPending"> Mostrar só pendentes
                        </label>
                        <button class="btn btn-outline btn-sm" onclick="exportCsv()">⬇️ Exportar CSV</button>
                    </div>
                    <div class="table-container">
                        <table class="table" id="finalsTable">
                            <thead>
                                <tr>
                                    <th>Participante</th>
                                    <th class="finals-cell">🥇 Campeão</th>
                                    <th class="finals-cell">🥈 Vice</th>
                                    <th class="finals-cell">🥉 3º lugar</th>
                                    <th class="finals-cell">4º lugar</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody id="finalsTableBody">
                                <tr><td colspan="6" class="text-center">Carregando...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Toast -->
    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js?v=202606121841"></script>
    <script src="/assets/js/admin-auth.js?v=202606121841"></script>
    <script src="/assets/js/flags.js?v=202606121841"></script>

    <script>
        const apiBase = '<?= $apiBase ?>';
        const token = getAdminToken();

        // Estado em memória
        let participants = [];        // [{id, name, uid}]
        let finalsByParticipant = {}; // participant_id -> {champion, runner_up, third_place, fourth_place}
        let outcome = {               // resultado oficial
            champion: null, runner_up: null, third_place: null, fourth_place: null
        };

        const POSITIONS = [
            { key: 'champion', label: '🥇' },
            { key: 'runner_up', label: '🥈' },
            { key: 'third_place', label: '🥉' },
            { key: 'fourth_place', label: '4º' }
        ];

        // Redireciona para o login se não autenticado
        if (!token) {
            window.location.href = '/admin/login.php';
        }

        async function loadData() {
            try {
                const [pRes, fRes, oRes] = await Promise.all([
                    fetch(`${apiBase}/participants`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }),
                    fetch(`${apiBase}/finals_predictions`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }),
                    fetch(`${apiBase}/tournament_outcome`)
                ]);

                if (!pRes.ok) throw new Error('Falha ao carregar participantes');
                participants = await pRes.json();
                const finals = fRes.ok ? await fRes.json() : [];
                const oData = oRes.ok ? await oRes.json() : {};
                outcome = {
                    champion: oData.champion || null,
                    runner_up: oData.runner_up || null,
                    third_place: oData.third_place || null,
                    fourth_place: oData.fourth_place || null
                };

                finalsByParticipant = {};
                finals.forEach(f => {
                    finalsByParticipant[f.participant_id] = f;
                });

                renderOutcome();
                renderStats();
                renderTable();
            } catch (error) {
                console.error('Error loading data:', error);
                showToast('Erro ao carregar palpites finais', 'error');
                document.getElementById('finalsTableBody').innerHTML =
                    '<tr><td colspan="6" class="text-center text-error">Erro ao carregar palpites</td></tr>';
            }
        }

        function hasOutcome() {
            return outcome.champion || outcome.runner_up || outcome.third_place || outcome.fourth_place;
        }

        function renderOutcome() {
            const banner = document.getElementById('outcomeBanner');
            const status = document.getElementById('outcomeStatus');

            if (!hasOutcome()) {
                banner.className = 'outcome-banner text-muted';
                banner.textContent = 'O resultado oficial ainda não foi definido nas Configurações.';
                status.textContent = 'Não definido';
                status.className = 'badge badge-warning';
                return;
            }

            status.textContent = 'Definido';
            status.className = 'badge badge-success';

            banner.className = 'outcome-banner';
            banner.innerHTML = POSITIONS.map(pos => {
                const team = outcome[pos.key];
                if (!team) {
                    return `<span class="outcome-item"><span class="pos-label">${pos.label}</span><span class="text-muted">—</span></span>`;
                }
                return `<span class="outcome-item"><span class="pos-label">${pos.label}</span>${getTeamHtml(team)}</span>`;
            }).join('');
        }

        function isComplete(f) {
            if (!f) return false;
            return f.champion && f.runner_up && f.third_place && f.fourth_place;
        }

        function renderStats() {
            const total = participants.length;
            const complete = participants.filter(p => isComplete(finalsByParticipant[p.id])).length;
            const pending = total - complete;
            document.getElementById('statTotal').textContent = `👥 Participantes: ${total}`;
            document.getElementById('statComplete').textContent = `✅ Completos: ${complete}`;
            document.getElementById('statPending').textContent = `⚠️ Pendentes: ${pending}`;
        }

        function cellHtml(team, posKey) {
            if (!team) return '<span class="text-muted italic">— Pendente</span>';
            const isHit = outcome[posKey] && outcome[posKey] === team;
            const hitBadge = isHit ? '<span class="hit-badge badge badge-success">✅ acertou</span>' : '';
            return `<div class="finals-cell">${getTeamHtml(team)}${hitBadge}</div>`;
        }

        function renderTable() {
            const search = document.getElementById('searchInput').value.trim().toLowerCase();
            const onlyPending = document.getElementById('onlyPending').checked;

            const filtered = participants
                .filter(p => {
                    if (onlyPending && isComplete(finalsByParticipant[p.id])) return false;
                    if (search && !p.name.toLowerCase().includes(search)) return false;
                    return true;
                })
                .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));

            const tbody = document.getElementById('finalsTableBody');
            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum participante encontrado.</td></tr>';
                return;
            }

            tbody.innerHTML = filtered.map(p => {
                const f = finalsByParticipant[p.id] || {};
                const complete = isComplete(f);
                const statusBadge = complete
                    ? '<span class="badge badge-success">Completo</span>'
                    : '<span class="badge badge-warning">Incompleto</span>';

                return `
                    <tr>
                        <td><strong>${escapeHtml(p.name)}</strong></td>
                        <td class="finals-cell">${cellHtml(f.champion, 'champion')}</td>
                        <td class="finals-cell">${cellHtml(f.runner_up, 'runner_up')}</td>
                        <td class="finals-cell">${cellHtml(f.third_place, 'third_place')}</td>
                        <td class="finals-cell">${cellHtml(f.fourth_place, 'fourth_place')}</td>
                        <td>${statusBadge}</td>
                    </tr>
                `;
            }).join('');
        }

        function escapeHtml(str) {
            if (str == null) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function exportCsv() {
            const rows = [['Participante', 'Campeao', 'Vice', '3 lugar', '4 lugar', 'Status']];
            participants
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
                .forEach(p => {
                    const f = finalsByParticipant[p.id] || {};
                    rows.push([
                        p.name,
                        f.champion || '',
                        f.runner_up || '',
                        f.third_place || '',
                        f.fourth_place || '',
                        isComplete(f) ? 'Completo' : 'Incompleto'
                    ]);
                });
            const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
            const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'palpites-finais.csv';
            a.click();
            URL.revokeObjectURL(url);
            showToast('⬇️ CSV exportado!', 'success');
        }

        // Filtros
        document.getElementById('searchInput').addEventListener('input', renderTable);
        document.getElementById('onlyPending').addEventListener('change', renderTable);

        loadData();
    </script>
</body>

</html>

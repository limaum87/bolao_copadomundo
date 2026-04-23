<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gerenciar Jogos - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div>
                    <h1>Gerenciar Jogos</h1>
                    <span class="header-subtitle">Cadastre e atualize os jogos da Copa</span>
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
                <a href="/admin/jogos.php" class="active">⚽ Jogos</a>
                <a href="/admin/configuracoes.php">⚙️ Configurações</a>
            </nav>

            <!-- Add Game Form -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">➕ Novo Jogo</h3>
                <form id="gameForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Data/Hora do Jogo</label>
                            <input type="datetime-local" name="kickoff" class="form-input" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Time A</label>
                            <input type="text" name="team_a" class="form-input" placeholder="Ex: Brasil" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Time B</label>
                            <input type="text" name="team_b" class="form-input" placeholder="Ex: Argentina" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">
                        💾 Salvar Jogo
                    </button>
                </form>
            </div>

            <!-- Games Table -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">⚽ Lista de Jogos</h3>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span id="gamesCount" class="badge badge-info"></span>
                        <input type="file" id="importFile" accept=".json" style="display: none;">
                        <button class="btn btn-sm btn-secondary"
                            onclick="document.getElementById('importFile').click()">
                            📥 Importar JSON
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteAllGames()">
                            🗑️ Apagar Todos
                        </button>
                    </div>
                </div>
                <div class="table-container">
                    <table class="table" id="gamesTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Data/Hora</th>
                                <th>Jogo</th>
                                <th>Placar Final</th>
                                <th>Status</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <!-- Score Modal -->
    <div id="scoreModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h4 class="modal-title" id="scoreModalTitle">Atualizar Placar</h4>
                <button type="button" class="modal-close" onclick="closeScoreModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="scoreForm">
                    <input type="hidden" name="game_id" id="scoreGameId">
                    <div class="text-center mb-lg">
                        <div class="game-teams">
                            <div class="team">
                                <div class="team-name" id="scoreTeamA">Time A</div>
                            </div>
                            <div class="game-vs">×</div>
                            <div class="team">
                                <div class="team-name" id="scoreTeamB">Time B</div>
                            </div>
                        </div>
                    </div>
                    <div class="score-input-group">
                        <input type="number" name="score_a" id="scoreA" class="score-input" min="0" max="99"
                            placeholder="0" required>
                        <span class="score-separator">×</span>
                        <input type="number" name="score_b" id="scoreB" class="score-input" min="0" max="99"
                            placeholder="0" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeScoreModal()">Cancelar</button>
                <button type="button" class="btn btn-primary" onclick="saveScore()">
                    💾 Salvar Placar
                </button>
            </div>
        </div>
    </div>

    <!-- Game Predictions Modal -->
    <div id="gamePredictionsModal" class="modal-overlay">
        <div class="modal" style="max-width: 600px;">
            <div class="modal-header">
                <h4 class="modal-title" id="gamePredictionsModalTitle">Palpites do Jogo</h4>
                <button type="button" class="modal-close" onclick="closeGamePredictionsModal()">&times;</button>
            </div>
            <div class="modal-body">
                <h5 class="mb-sm">✅ Palpites Realizados</h5>
                <div id="gamePredictionsList" class="table-container mb-lg">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Participante</th>
                                <th>Palpite</th>
                            </tr>
                        </thead>
                        <tbody id="gamePredictionsTableBody"></tbody>
                    </table>
                </div>

                <h5 class="mb-sm text-error">⚠️ Faltam palpitar</h5>
                <div id="missingPredictionsList" class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Participante</th>
                                <th>Ação</th>
                            </tr>
                        </thead>
                        <tbody id="missingPredictionsTableBody"></tbody>
                    </table>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeGamePredictionsModal()">Fechar</button>
            </div>
        </div>
    </div>


    <script src="/assets/js/flags.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js"></script>
    <script>
        const apiBase = '<?= $apiBase ?>';
        const token = localStorage.getItem('admin_token');

        if (!token) {
            window.location.href = '/admin/login.php';
        }

        function formatDate(isoString) {
            const date = new Date(isoString);
            return date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        function isGameOpen(kickoff) {
            return new Date(kickoff) > new Date();
        }

        async function loadGames() {
            try {
                const res = await fetch(`${apiBase}/games`);
                const games = await res.json();

                document.getElementById('gamesCount').textContent = `${games.length} jogos`;

                const tbody = document.querySelector('#gamesTable tbody');
                tbody.innerHTML = games.map(game => {
                    const isOpen = isGameOpen(game.kickoff);
                    const hasScore = game.score_a !== null && game.score_b !== null;

                    return `
                        <tr>
                            <td>${game.id}</td>
                            <td>${formatDate(game.kickoff)}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    ${getTeamHtml(game.team_a)} <span>×</span> ${getTeamHtml(game.team_b)}
                                </div>
                            </td>
                            <td>
                                ${hasScore
                            ? `<span style="font-size: 1.25rem; font-weight: 700;">${game.score_a} × ${game.score_b}</span>`
                            : '<span class="text-muted">-</span>'
                        }
                            </td>
                            <td>
                                <span class="badge ${isOpen ? 'badge-success' : 'badge-warning'}">
                                    ${isOpen ? 'Aberto' : 'Encerrado'}
                                </span>
                            </td>
                            <td>
                                <div class="flex gap-sm">
                                    <button class="btn btn-sm btn-outline" onclick="openGamePredictionsModal(${game.id}, '${game.team_a}', '${game.team_b}')" title="Ver palpites deste jogo">
                                        👁️ Palpites
                                    </button>
                                    <button class="btn btn-sm btn-primary" onclick="openScoreModal(${game.id}, '${game.team_a}', '${game.team_b}', ${game.score_a ?? 'null'}, ${game.score_b ?? 'null'})">
                                        📝 Placar
                                    </button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteGame(${game.id})">
                                        🗑️
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');

            } catch (error) {
                console.error('Error loading games:', error);
                showToast('Erro ao carregar jogos', 'error');
            }
        }

        // Add new game
        document.getElementById('gameForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const kickoffLocal = formData.get('kickoff');
            const data = {
                kickoff: kickoffLocal,
                team_a: formData.get('team_a'),
                team_b: formData.get('team_b')
            };

            try {
                const res = await fetch(`${apiBase}/games`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('✅ Jogo adicionado!', 'success');
                    e.target.reset();
                    loadGames();
                } else {
                    showToast('Erro ao salvar jogo', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });

        // Delete game
        async function deleteGame(id) {
            if (!confirm('Tem certeza que deseja apagar este jogo?')) return;

            try {
                await fetch(`${apiBase}/games/${id}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                showToast('🗑️ Jogo removido', 'success');
                loadGames();
            } catch (error) {
                showToast('Erro ao remover jogo', 'error');
            }
        }

        // Delete all games
        async function deleteAllGames() {
            if (!confirm('⚠️ Tem certeza que deseja apagar TODOS os jogos?\n\nIsso também apagará todos os palpites!')) return;
            if (!confirm('⚠️ Esta ação é IRREVERSÍVEL!\n\nClique OK para confirmar.')) return;

            try {
                const res = await fetch(`${apiBase}/games/all`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    showToast(`🗑️ ${data.deleted} jogos removidos!`, 'success');
                    loadGames();
                } else {
                    showToast('Erro ao remover jogos', 'error');
                }
            } catch (error) {
                showToast('Erro ao remover jogos', 'error');
            }
        }

        // Import games from JSON
        document.getElementById('importFile').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            try {
                const text = await file.text();
                const games = JSON.parse(text);

                if (!Array.isArray(games)) {
                    showToast('O arquivo deve conter um array de jogos', 'error');
                    return;
                }

                const res = await fetch(`${apiBase}/games/import`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: text
                });

                if (res.ok) {
                    const data = await res.json();
                    showToast(`✅ ${data.imported} jogos importados!`, 'success');
                    loadGames();
                } else {
                    showToast('Erro ao importar jogos', 'error');
                }
            } catch (error) {
                showToast('Erro ao ler arquivo JSON', 'error');
            }

            // Reset input para permitir reimportar o mesmo arquivo
            e.target.value = '';
        });

        // Score modal
        const scoreModal = document.getElementById('scoreModal');

        function openScoreModal(id, teamA, teamB, scoreA, scoreB) {
            document.getElementById('scoreGameId').value = id;
            document.getElementById('scoreTeamA').innerHTML = getTeamHtml(teamA);
            document.getElementById('scoreTeamB').innerHTML = getTeamHtml(teamB);
            document.getElementById('scoreModalTitle').textContent = `${teamA} × ${teamB}`;
            document.getElementById('scoreA').value = scoreA !== null ? scoreA : '';
            document.getElementById('scoreB').value = scoreB !== null ? scoreB : '';
            scoreModal.classList.add('active');
            document.getElementById('scoreA').focus();
        }

        function closeScoreModal() {
            scoreModal.classList.remove('active');
        }

        async function saveScore() {
            const id = document.getElementById('scoreGameId').value;
            const scoreA = parseInt(document.getElementById('scoreA').value, 10);
            const scoreB = parseInt(document.getElementById('scoreB').value, 10);

            if (isNaN(scoreA) || isNaN(scoreB)) {
                showToast('Preencha ambos os placares', 'warning');
                return;
            }

            try {
                const res = await fetch(`${apiBase}/games/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ score_a: scoreA, score_b: scoreB })
                });

                if (res.ok) {
                    showToast('✅ Placar atualizado!', 'success');
                    closeScoreModal();
                    loadGames();
                } else {
                    showToast('Erro ao atualizar placar', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        }

        // Close modal on ESC or overlay click
        scoreModal.addEventListener('click', (e) => {
            if (e.target === scoreModal) closeScoreModal();
        });

        // Game Predictions Modal Logic
        const gamePredictionsModal = document.getElementById('gamePredictionsModal');

        async function openGamePredictionsModal(gameId, teamA, teamB) {
            document.getElementById('gamePredictionsModalTitle').textContent = `Palpites: ${teamA} × ${teamB}`;
            const tbody = document.getElementById('gamePredictionsTableBody');
            const missingTbody = document.getElementById('missingPredictionsTableBody');

            tbody.innerHTML = '<tr><td colspan="2" class="text-center">Carregando...</td></tr>';
            missingTbody.innerHTML = '<tr><td colspan="2" class="text-center">Carregando...</td></tr>';

            gamePredictionsModal.classList.add('active');

            try {
                const [predRes, partRes] = await Promise.all([
                    fetch(`${apiBase}/predictions?game_id=${gameId}`),
                    fetch(`${apiBase}/participants`)
                ]);

                const predictions = await predRes.json();
                const allParticipants = await partRes.json();

                // Palpites realizados
                if (predictions.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Nenhum palpite ainda</td></tr>';
                } else {
                    tbody.innerHTML = predictions.map(p => `
                        <tr>
                            <td><strong>${p.participant_name}</strong></td>
                            <td><span style="font-size: 1.1rem;">${p.goals_a} × ${p.goals_b}</span></td>
                        </tr>
                    `).join('');
                }

                // Participantes faltando
                const predictedIds = new Set(predictions.map(p => p.participant_id));
                const missing = allParticipants.filter(p => !predictedIds.has(p.id));

                if (missing.length === 0) {
                    missingTbody.innerHTML = '<tr><td colspan="2" class="text-center text-success">Todos já palpitaram! 🎉</td></tr>';
                } else {
                    missingTbody.innerHTML = missing.map(p => `
                        <tr>
                            <td>${p.name}</td>
                            <td>
                                <a href="https://wa.me/?text=${encodeURIComponent('Oi ' + p.name + '! Vi que você ainda não palpitou no jogo ' + teamA + ' × ' + teamB + '. Não esquece! ⚽🏆')}" 
                                   target="_blank" class="btn btn-sm btn-outline" style="padding: 2px 8px; font-size: 0.75rem;">
                                   📢 Avisar
                                </a>
                            </td>
                        </tr>
                    `).join('');
                }

            } catch (error) {
                console.error(error);
                tbody.innerHTML = '<tr><td colspan="2" class="text-center text-error">Erro ao carregar dados</td></tr>';
            }
        }

        function closeGamePredictionsModal() {
            gamePredictionsModal.classList.remove('active');
        }

        gamePredictionsModal.addEventListener('click', (e) => {
            if (e.target === gamePredictionsModal) closeGamePredictionsModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeScoreModal();
                closeGamePredictionsModal();
            }
        });

        loadGames();
    </script>
</body>

</html>
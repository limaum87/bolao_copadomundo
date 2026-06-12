<?php
require_once __DIR__ . '/../config.php';
$uid = $_GET['uid'] ?? ($_SERVER['PATH_INFO'] ?? '');
$uid = trim($uid, '/');
if (!$uid) {
    die('UID não informado');
}
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meus Palpites - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606121643">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div>
                    <h1>Bolão Copa 2026</h1>
                    <span class="header-subtitle">Seus palpites para a Copa do Mundo</span>
                </div>
                <div class="badge badge-info" style="background: rgba(255,255,255,0.2); color: white;" id="participantBadge">
                    🎯 Participante: <?= htmlspecialchars($uid) ?>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
        <div class="container">
            <!-- Live Match Card -->
            <div id="liveCard" class="live-card" style="display: none;">
                <div id="liveCardContent"></div>
            </div>

            <!-- Loading State -->
            <div id="loadingState" class="loading-container">
                <div class="spinner"></div>
            </div>

            <!-- Dashboard Section -->
            <section id="dashboardSection" style="display: none;">
                <div class="form-row" style="grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));">
                    <div class="card text-center" style="cursor: pointer; transition: transform 0.2s;"
                        onclick="showView('games')" onmouseover="this.style.transform='translateY(-5px)'"
                        onmouseout="this.style.transform='translateY(0)'">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">⚽</div>
                        <h3>Meus Palpites</h3>
                        <p class="text-muted mb-md">Palpites para os jogos da Copa</p>
                        <div id="gamesStatusBadge" class="badge badge-warning">Carregando...</div>
                    </div>
                    <div class="card text-center" style="cursor: pointer; transition: transform 0.2s;"
                        onclick="showView('finals')" onmouseover="this.style.transform='translateY(-5px)'"
                        onmouseout="this.style.transform='translateY(0)'">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🥇</div>
                        <h3>Finais</h3>
                        <p class="text-muted mb-md">Escolha quem será o campeão</p>
                        <div id="finalsStatusBadge" class="badge badge-warning">Pendente</div>
                    </div>
                    <div class="card text-center" style="cursor: pointer; transition: transform 0.2s;"
                        onclick="showView('ranking')" onmouseover="this.style.transform='translateY(-5px)'"
                        onmouseout="this.style.transform='translateY(0)'">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🏆</div>
                        <h3>Ranking</h3>
                        <p class="text-muted mb-md">Veja sua posição na tabela</p>
                        <div class="badge badge-info">Ver Classificação</div>
                    </div>
                </div>
            </section>

            <!-- Games View -->
            <div id="gamesView" style="display: none;">
                <button class="btn btn-outline mb-lg" onclick="showView('dashboard')">← Voltar ao Menu</button>

                <section id="gamesSection">
                    <div class="card-header" style="border: none; padding: 0;">
                        <h2>⚽ Jogos da Copa</h2>
                        <span id="gamesCount" class="badge badge-success"></span>
                    </div>
                    <div class="filter-bar" style="display: flex; gap: var(--space-sm); margin-bottom: var(--space-lg); flex-wrap: wrap;">
                        <button class="btn btn-sm btn-primary filter-btn" data-filter="open" onclick="setFilter('open')">🕐 Próximos jogos</button>
                        <button class="btn btn-sm btn-outline filter-btn" data-filter="missing" onclick="setFilter('missing')">🎯 Faltam palpites</button>
                        <button class="btn btn-sm btn-outline filter-btn" data-filter="all" onclick="setFilter('all')">📋 Todos</button>
                    </div>
                    <div id="gamesGrid" class="games-grid"></div>
                    <div id="emptyFilterMsg" class="text-center text-muted" style="display: none; padding: var(--space-xl) 0;">
                        <div style="font-size: 2rem; margin-bottom: var(--space-sm);">🎉</div>
                        Nenhum jogo encontrado para este filtro.
                    </div>
                </section>

                <!-- Scoring Rules -->
                <section class="card mt-xl" id="scoringRulesSection">
                    <h3 class="card-title mb-lg">📊 Regras de Pontuação</h3>
                    <div class="form-row" id="scoringRulesContent">
                        <div>
                            <strong class="text-success" id="ruleExactScore">-- pontos</strong>
                            <p class="text-muted">Placar exato</p>
                        </div>
                        <div>
                            <strong class="text-warning" id="ruleCorrectResult">-- pontos</strong>
                            <p class="text-muted">Apenas resultado</p>
                        </div>
                        <div>
                            <strong style="color: var(--color-blue);" id="rulePartialScore">-- pontos</strong>
                            <p class="text-muted">Placar parcial</p>
                        </div>
                    </div>
                </section>
            </div>

            <!-- Finals View -->
            <div id="finalsView" style="display: none;">
                <button class="btn btn-outline mb-lg" onclick="showView('dashboard')">← Voltar ao Menu</button>

                <section class="finals-section" id="finalsSection">
                    <h3 class="finals-title">Palpite Final - Classificação</h3>
                    <p class="text-muted mb-lg text-center">Escolha os times que ficarão nas primeiras posições. Estes
                        palpites valem muitos pontos!</p>
                    <form id="finalsForm">
                        <input type="hidden" name="participant_uid" value="<?= $uid ?>">
                        <div class="finals-grid">
                            <div class="final-input-group">
                                <label class="final-input-label">🥇 Campeão</label>
                                <select name="champion" class="final-input" required></select>
                            </div>
                            <div class="final-input-group">
                                <label class="final-input-label">🥈 Vice-campeão</label>
                                <select name="runner_up" class="final-input" required></select>
                            </div>
                            <div class="final-input-group">
                                <label class="final-input-label">🥉 3º Lugar</label>
                                <select name="third_place" class="final-input" required></select>
                            </div>
                            <div class="final-input-group">
                                <label class="final-input-label">4️⃣ 4º Lugar</label>
                                <select name="fourth_place" class="final-input" required></select>
                            </div>
                        </div>
                        <div class="mt-lg text-center">
                            <button type="submit" class="btn btn-secondary btn-lg">
                                💾 Salvar Palpite Final
                            </button>
                        </div>
                    </form>
                </section>
            </div>

            <!-- Ranking View -->
            <div id="rankingView" style="display: none;">
                <button class="btn btn-outline mb-lg" onclick="showView('dashboard')">← Voltar ao Menu</button>
                <div class="card">
                    <h3 class="card-title mb-lg">🏆 Ranking Geral</h3>
                    <div id="rankingContainer">
                        <div class="loading-container">
                            <div class="spinner"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Prediction Modal -->
    <div id="predictionModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h4 class="modal-title" id="modalTitle">Fazer Palpite</h4>
                <button type="button" class="modal-close" id="closeModal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="predictionForm">
                    <input type="hidden" name="game_id" id="modalGameId">
                    <input type="hidden" name="participant_uid" value="<?= $uid ?>">

                    <div class="text-center mb-lg">
                        <div class="game-teams">
                            <div class="team">
                                <div class="team-name" id="modalTeamA">Time A</div>
                            </div>
                            <div class="game-vs">×</div>
                            <div class="team">
                                <div class="team-name" id="modalTeamB">Time B</div>
                            </div>
                        </div>
                    </div>

                    <div class="score-input-group">
                        <input type="number" name="goals_a" id="modalGoalsA" class="score-input" min="0" max="99"
                            placeholder="0" required>
                        <span class="score-separator">×</span>
                        <input type="number" name="goals_b" id="modalGoalsB" class="score-input" min="0" max="99"
                            placeholder="0" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" id="cancelModal">Cancelar</button>
                <button type="button" class="btn btn-primary" id="savePrediction">
                    💾 Salvar Palpite
                </button>
            </div>
        </div>
    </div>
    <!-- Score Breakdown Modal -->
    <div id="scoreBreakdownModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h4 class="modal-title" id="breakdownTitle">Detalhamento de Pontos</h4>
                <button type="button" class="modal-close" onclick="closeBreakdownModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div id="breakdownLoading" class="text-center py-lg">
                    <div class="spinner" style="margin: 0 auto;"></div>
                </div>
                <div id="breakdownContent" style="display: none;">
                    <ul id="breakdownList" class="breakdown-list"></ul>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeBreakdownModal()">Fechar</button>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js?v=202606121643"></script>

    <script src="/assets/js/flags.js?v=202606121643"></script>
    <script>
        const apiBase = '<?= $apiBase ?>';
        const uid = '<?= $uid ?>';
        let participantName = '';
        let gamesData = [];
        let predictionsData = [];
        let scoringConfig = null;
        let currentFilter = 'open';

        // Populate finals selects with teams from countryCodes
        function populateFinalsSelects() {
            const teams = Object.keys(countryCodes).sort((a, b) => a.localeCompare(b, 'pt-BR'));
            const selects = document.querySelectorAll('#finalsForm select');
            selects.forEach(select => {
                select.innerHTML = '<option value="">Selecione...</option>' +
                    teams.map(t => `<option value="${t}">${t}</option>`).join('');
            });
        }
        populateFinalsSelects();

        function setFinalsSelectValue(name, value) {
            const select = document.querySelector(`#finalsForm [name=${name}]`);
            if (select && value) select.value = value;
        }

        // Load scoring config and update rules display
        async function loadScoringConfig() {
            try {
                const res = await fetch(`${apiBase}/scoring_config`);
                if (res.ok) {
                    scoringConfig = await res.json();
                    document.getElementById('ruleExactScore').textContent = `${scoringConfig.exact_score} pontos`;
                    document.getElementById('ruleCorrectResult').textContent = `${scoringConfig.correct_result} pontos`;
                    document.getElementById('rulePartialScore').textContent = `${scoringConfig.partial_score} pontos`;

                    // Check finals deadline
                    if (scoringConfig.finals_deadline) {
                        const deadline = new Date(scoringConfig.finals_deadline);
                        const now = new Date();
                        const isExpired = now > deadline;
                        const finalsForm = document.getElementById('finalsForm');
                        const finalsSection = document.getElementById('finalsSection');

                        if (isExpired) {
                            // Disable form
                            finalsForm.querySelectorAll('select, button').forEach(el => el.disabled = true);
                            const warning = document.createElement('div');
                            warning.className = 'alert alert-error text-center mt-md';
                            warning.textContent = `⏰ O prazo para palpites finais encerrou em ${deadline.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'})}.`;
                            finalsSection.querySelector('.finals-grid').after(warning);
                        } else {
                            // Show countdown hint
                            const hint = document.createElement('div');
                            hint.className = 'text-muted text-center mt-md';
                            hint.style.fontSize = '0.85rem';
                            hint.textContent = `⏰ Prazo: ${deadline.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'})}`;
                            finalsSection.querySelector('.finals-grid').after(hint);
                        }
                    }
                }
            } catch (error) {
                console.error('Error loading scoring config:', error);
            }
        }
        loadScoringConfig();

        // Format date for display
        function formatDate(isoString) {
            const date = new Date(isoString);
            const options = {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            };
            return date.toLocaleDateString('pt-BR', options);
        }

        // Check if game is open for predictions
        function isGameOpen(kickoff) {
            return new Date(kickoff) > new Date();
        }

        function getFilteredGames() {
            if (currentFilter === 'open') {
                return gamesData.filter(g => isGameOpen(g.kickoff));
            } else if (currentFilter === 'missing') {
                return gamesData.filter(g => {
                    const hasPred = predictionsData.some(p => p.game_id === g.id);
                    return !hasPred && isGameOpen(g.kickoff);
                });
            }
            return gamesData;
        }

        function setFilter(filter) {
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.className = btn.dataset.filter === filter
                    ? 'btn btn-sm btn-primary filter-btn'
                    : 'btn btn-sm btn-outline filter-btn';
            });
            renderGames();
        }

        function renderGames() {
            const grid = document.getElementById('gamesGrid');
            const emptyMsg = document.getElementById('emptyFilterMsg');
            grid.innerHTML = '';

            const filtered = getFilteredGames();

            if (filtered.length === 0) {
                emptyMsg.style.display = 'block';
            } else {
                emptyMsg.style.display = 'none';
            }

            filtered.forEach(game => {
                const myPred = predictionsData.find(p => p.game_id === game.id);
                const isOpen = isGameOpen(game.kickoff);

                const card = document.createElement('div');
                card.className = 'game-card';
                card.innerHTML = `
                    <div class="game-card-header">
                        <span>📅 ${formatDate(game.kickoff)}</span>
                        <span class="badge ${isOpen ? 'badge-success' : 'badge-danger'}">
                            <span class="status-dot ${isOpen ? 'open' : 'closed'}"></span>
                            ${isOpen ? 'Aberto' : 'Encerrado'}
                        </span>
                    </div>
                    <div class="game-card-body">
                        <div class="game-teams">
                            <div class="team">
                                <div class="team-name">${getTeamHtml(game.team_a)}</div>
                            </div>
                            <div class="game-vs">×</div>
                            <div class="team">
                                <div class="team-name">${getTeamHtml(game.team_b)}</div>
                            </div>
                        </div>
                        <div class="game-prediction">
                            <div class="game-prediction-label">Seu palpite</div>
                            ${myPred
                        ? `<div class="game-prediction-score">${myPred.goals_a} × ${myPred.goals_b}</div>`
                        : `<div class="game-prediction-empty">Nenhum palpite</div>`
                    }
                        </div>
                    </div>
                    <div class="game-card-footer">
                        <button 
                            class="btn ${isOpen ? 'btn-primary' : 'btn-outline'} btn-block predict-btn"
                            data-game-id="${game.id}"
                            data-team-a="${game.team_a}"
                            data-team-b="${game.team_b}"
                            data-goals-a="${myPred?.goals_a ?? ''}"
                            data-goals-b="${myPred?.goals_b ?? ''}"
                            ${!isOpen ? 'disabled' : ''}
                        >
                            ${isOpen
                        ? (myPred ? '✏️ Editar palpite' : '🎯 Fazer palpite')
                        : '🔒 Encerrado'
                    }
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });

            // Update games count
            const openGames = gamesData.filter(g => isGameOpen(g.kickoff)).length;
            const missingCount = gamesData.filter(g => {
                const hasPred = predictionsData.some(p => p.game_id === g.id);
                return !hasPred && isGameOpen(g.kickoff);
            }).length;
            const predictedCount = predictionsData.length;
            const label = currentFilter === 'missing'
                ? `${missingCount} faltam palpites`
                : currentFilter === 'open'
                    ? `${openGames} jogos abertos`
                    : `${gamesData.length} jogos`;
            document.getElementById('gamesCount').textContent = label;

            const gamesBadge = document.getElementById('gamesStatusBadge');
            gamesBadge.textContent = `${predictedCount} / ${gamesData.length} palpites`;
            gamesBadge.className = `badge ${predictedCount === gamesData.length ? 'badge-success' : 'badge-warning'}`;
        }

        let currentView = 'dashboard';

        // Load data
        async function loadData() {
            try {
                const [gamesRes, predRes, finalsRes] = await Promise.all([
                    fetch(`${apiBase}/games`),
                    fetch(`${apiBase}/predictions?participant_uid=${uid}`),
                    fetch(`${apiBase}/finals_predictions?participant_uid=${uid}`)
                ]);

                gamesData = await gamesRes.json();
                predictionsData = await predRes.json();
                const finals = await finalsRes.json();
                const myFinals = finals[0];

                // Hide loading
                document.getElementById('loadingState').style.display = 'none';

                renderGames();

                // Fill finals form
                const finalsBadge = document.getElementById('finalsStatusBadge');
                if (myFinals) {
                    ['champion', 'runner_up', 'third_place', 'fourth_place'].forEach(field => {
                        if (myFinals[field]) setFinalsSelectValue(field, myFinals[field]);
                    });

                    const isComplete = myFinals.champion && myFinals.runner_up && myFinals.third_place && myFinals.fourth_place;
                    finalsBadge.textContent = isComplete ? '✅ Completo' : '⚠️ Incompleto';
                    finalsBadge.className = `badge ${isComplete ? 'badge-success' : 'badge-warning'}`;
                } else {
                    finalsBadge.textContent = '⚠️ Pendente';
                    finalsBadge.className = 'badge badge-warning';
                }

                if (currentView === 'dashboard') {
                    document.getElementById('dashboardSection').style.display = 'block';
                } else {
                    showView(currentView);
                }
            } catch (error) {
                console.error('Error loading data:', error);
                showToast('Erro ao carregar dados', 'error');
            }
        }

        // Modal handling
        const modal = document.getElementById('predictionModal');

        function openModal(gameId, teamA, teamB, goalsA, goalsB) {
            document.getElementById('modalGameId').value = gameId;
            document.getElementById('modalTeamA').innerHTML = getTeamHtml(teamA);
            document.getElementById('modalTeamB').innerHTML = getTeamHtml(teamB);
            document.getElementById('modalGoalsA').value = goalsA;
            document.getElementById('modalGoalsB').value = goalsB;
            document.getElementById('modalTitle').textContent = `${teamA} × ${teamB}`;
            modal.classList.add('active');
            document.getElementById('modalGoalsA').focus();
        }

        function closeModal() {
            modal.classList.remove('active');
        }

        // Event listeners
        document.getElementById('gamesGrid').addEventListener('click', (e) => {
            const btn = e.target.closest('.predict-btn');
            if (!btn || btn.disabled) return;

            openModal(
                btn.dataset.gameId,
                btn.dataset.teamA,
                btn.dataset.teamB,
                btn.dataset.goalsA,
                btn.dataset.goalsB
            );
        });

        document.getElementById('closeModal').addEventListener('click', closeModal);
        document.getElementById('cancelModal').addEventListener('click', closeModal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });

        document.getElementById('savePrediction').addEventListener('click', async () => {
            const form = document.getElementById('predictionForm');
            const formData = new FormData(form);
            const data = {
                participant_uid: uid,
                game_id: parseInt(formData.get('game_id'), 10),
                goals_a: parseInt(formData.get('goals_a'), 10),
                goals_b: parseInt(formData.get('goals_b'), 10)
            };

            if (isNaN(data.goals_a) || isNaN(data.goals_b)) {
                showToast('Por favor, preencha ambos os placares', 'warning');
                return;
            }

            try {
                const res = await fetch(`${apiBase}/predictions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('✅ Palpite salvo com sucesso!', 'success');
                    closeModal();
                    loadData();
                } else {
                    const msg = await res.json();
                    showToast(msg.error || 'Erro ao salvar palpite', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });

        document.getElementById('finalsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.target));

            try {
                const res = await fetch(`${apiBase}/finals_predictions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('🏆 Palpite final salvo!', 'success');
                    const finalsBadge = document.getElementById('finalsStatusBadge');
                    finalsBadge.textContent = '✅ Completo';
                    finalsBadge.className = 'badge badge-success';
                } else {
                    showToast('Erro ao salvar palpite final', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
            if (e.key === 'Enter' && modal.classList.contains('active')) {
                document.getElementById('savePrediction').click();
            }
        });

        // Navigation
        function showView(viewName) {
            currentView = viewName;

            // Hide all views
            document.getElementById('dashboardSection').style.display = 'none';
            document.getElementById('gamesView').style.display = 'none';
            document.getElementById('finalsView').style.display = 'none';
            document.getElementById('rankingView').style.display = 'none';

            // Show selected view
            if (viewName === 'dashboard') {
                document.getElementById('dashboardSection').style.display = 'block';
            } else if (viewName === 'games') {
                document.getElementById('gamesView').style.display = 'block';
            } else if (viewName === 'finals') {
                document.getElementById('finalsView').style.display = 'block';
            } else if (viewName === 'ranking') {
                document.getElementById('rankingView').style.display = 'block';
                loadRanking();
            }
        }

        // Load Ranking
        async function loadRanking() {
            try {
                const res = await fetch(`${apiBase}/scores`);
                const scores = await res.json();

                const rankingHtml = scores.length > 0
                    ? `<table class="table">
                        <thead>
                            <tr><th>#</th><th>Participante</th><th>Pontos</th></tr>
                        </thead>
                        <tbody>
                            ${scores.map((s, i) => `
                                <tr class="${s.uid === uid ? 'highlight-row' : ''}" style="${s.uid === uid ? 'background-color: rgba(254, 221, 0, 0.1);' : ''}">
                                    <td>${i + 1}</td>
                                    <td>
                                        ${s.name}
                                        ${s.uid === uid ? '<span class="badge badge-info" style="margin-left: 8px;">Você</span>' : ''}
                                    </td>
                                    <td>
                                        <button class="btn btn-sm btn-outline" style="min-width: 60px; font-weight: 800;" onclick="openBreakdownModal(${s.id}, '${s.name}')">
                                            ${s.total_points || 0}
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>`
                    : '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">Nenhum ranking disponível ainda</div></div>';

                document.getElementById('rankingContainer').innerHTML = rankingHtml;
            } catch (error) {
                console.error('Error loading ranking:', error);
                document.getElementById('rankingContainer').innerHTML = '<div class="alert alert-error">Erro ao carregar ranking</div>';
            }
        }

        // Score Breakdown
        const breakdownModal = document.getElementById('scoreBreakdownModal');

        async function openBreakdownModal(participantId, name) {
            document.getElementById('breakdownTitle').textContent = `Palpites de ${name}`;
            document.getElementById('breakdownLoading').style.display = 'block';
            document.getElementById('breakdownContent').style.display = 'none';
            document.getElementById('breakdownList').innerHTML = '';

            breakdownModal.classList.add('active');

            try {
                const res = await fetch(`${apiBase}/scores/${participantId}/details`);
                const data = await res.json();

                document.getElementById('breakdownLoading').style.display = 'none';
                document.getElementById('breakdownContent').style.display = 'block';

                if (data.breakdown.length === 0) {
                    document.getElementById('breakdownList').innerHTML = '<li class="text-center py-lg text-muted">Ainda não marcou pontos</li>';
                } else {
                    document.getElementById('breakdownList').innerHTML = data.breakdown.map(item => `
                        <li class="breakdown-item">
                            <div class="breakdown-desc">${item.description}</div>
                            <div class="breakdown-pts pts-${item.points}">${item.points} pts</div>
                        </li>
                    `).join('');
                }
            } catch (error) {
                console.error(error);
                document.getElementById('breakdownLoading').innerHTML = '<div class="text-error">Erro ao carregar detalhes</div>';
            }
        }

        function closeBreakdownModal() {
            breakdownModal.classList.remove('active');
        }

        breakdownModal.addEventListener('click', (e) => {
            if (e.target === breakdownModal) closeBreakdownModal();
        });

        // ---- Live Match Card ----
        function liveTeamHtml(name) {
            // Versão simplificada para o card ao vivo: bandeira + nome empilhados verticalmente
            const flagUrl = getFlagUrl(name);
            if (flagUrl) {
                return `<div class="live-team">
                    <img src="${flagUrl}" alt="${name}" class="team-flag">
                    <span class="team-name">${name}</span>
                </div>`;
            }
            return `<div class="live-team"><span class="team-name">${name}</span></div>`;
        }

        async function loadLiveCard() {
            try {
                const res = await fetch(`${apiBase}/live`);
                if (!res.ok) return;
                const data = await res.json();
                const card = document.getElementById('liveCard');
                const content = document.getElementById('liveCardContent');

                const liveGames = data.live || [];
                const nextGame = data.next || null;

                if (liveGames.length > 0) {
                    // Jogo AO VIVO — mostra placar + palpites
                    const g = liveGames[0];
                    const preds = g.predictions || [];
                    let predsHtml = '';
                    if (preds.length > 0) {
                        predsHtml = `<div class="live-predictions">
                            <div class="live-predictions-title">🎯 Palpites do Bolão</div>
                            <div class="live-predictions-grid">
                                ${preds.map(p => `
                                    <div class="live-prediction-item">
                                        <span class="live-prediction-name">${p.participant_name}</span>
                                        <span class="live-prediction-score">${p.goals_a} × ${p.goals_b}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>`;
                    } else {
                        predsHtml = '<div class="text-muted text-center" style="padding: 8px; font-size: 0.85rem;">Nenhum palpite ainda</div>';
                    }

                    content.innerHTML = `
                        <div class="live-header">
                            <span class="live-badge-live">🔴 AO VIVO</span>
                            <span class="live-clock">${g.clock || ''}</span>
                        </div>
                        <div class="live-score-section">
                            ${liveTeamHtml(g.home)}
                            <div class="live-score-box">
                                <span class="live-score-num">${g.score_a}</span>
                                <span class="live-score-x">×</span>
                                <span class="live-score-num">${g.score_b}</span>
                            </div>
                            ${liveTeamHtml(g.away)}
                        </div>
                        ${predsHtml}
                    `;
                    card.className = 'live-card live-card-active';
                    card.style.display = 'block';
                } else if (nextGame) {
                    // Sem jogo ao vivo — mostra próximo
                    content.innerHTML = `
                        <div class="live-header">
                            <span class="live-badge-next">⏳ PRÓXIMO JOGO</span>
                        </div>
                        <div class="live-score-section">
                            ${liveTeamHtml(nextGame.home)}
                            <div class="live-score-box">
                                <span class="live-score-x">×</span>
                            </div>
                            ${liveTeamHtml(nextGame.away)}
                        </div>
                        <div class="live-next-detail">${nextGame.detail || ''}</div>
                    `;
                    card.className = 'live-card live-card-next';
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            } catch (error) {
                console.error('Error loading live card:', error);
            }
        }

        // Refresh live card every 60 seconds
        loadLiveCard();
        setInterval(loadLiveCard, 60000);

        // Load participant name
        async function loadParticipantName() {
            try {
                const res = await fetch(`${apiBase}/scores`);
                if (res.ok) {
                    const scores = await res.json();
                    const me = scores.find(s => s.uid === uid);
                    if (me) {
                        participantName = me.name;
                        document.getElementById('participantBadge').innerHTML = `🎯 <strong>${participantName}</strong>`;
                    }
                }
            } catch (error) {
                console.error('Error loading participant name:', error);
            }
        }

        // Initialize
        loadParticipantName();
        loadData();
    </script>
</body>

</html>
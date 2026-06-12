<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606121841">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div>
                    <h1>Admin - Bolão Copa 2026</h1>
                    <span class="header-subtitle">Painel de Controle</span>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="openChangePasswordModal()" class="btn btn-outline btn-sm">🔑 Alterar Senha</button>
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
                <a href="/admin/index.php" class="active">🏠 Dashboard</a>
                <a href="/admin/participantes.php">👥 Participantes</a>
                <a href="/admin/jogos.php">⚽ Jogos</a>
                <a href="/admin/configuracoes.php">⚙️ Configurações</a>
            </nav>

            <!-- Stats Cards -->
            <div class="form-row mb-xl">
                <div class="card text-center">
                    <div style="font-size: 3rem;">👥</div>
                    <div id="participantsCount" style="font-size: 2rem; font-weight: 700; color: var(--color-green);">-
                    </div>
                    <div class="text-muted">Participantes</div>
                </div>
                <div class="card text-center">
                    <div style="font-size: 3rem;">⚽</div>
                    <div id="gamesCount" style="font-size: 2rem; font-weight: 700; color: var(--color-blue);">-</div>
                    <div class="text-muted">Jogos cadastrados</div>
                </div>
                <div class="card text-center">
                    <div style="font-size: 3rem;">🎯</div>
                    <div id="predictionsCount"
                        style="font-size: 2rem; font-weight: 700; color: var(--color-yellow-dark);">-</div>
                    <div class="text-muted">Palpites registrados</div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="card">
                <h3 class="card-title mb-lg">🚀 Ações Rápidas</h3>
                <div class="form-row">
                    <a href="/admin/participantes.php" class="btn btn-primary btn-lg btn-block">
                        ➕ Adicionar Participante
                    </a>
                    <a href="/admin/jogos.php" class="btn btn-outline btn-lg btn-block">
                        ➕ Adicionar Jogo
                    </a>
                </div>
            </div>

            <!-- Quick Score Update -->
            <div class="card mt-xl" id="quickScoreCard" style="display:none;">
                <h3 class="card-title mb-lg">⚡ Resultado do Jogo</h3>
                <div id="quickScoreContent" class="quick-score-content">
                    <div class="quick-score-loading" style="text-align:center; padding:20px;">
                        <div class="spinner" style="margin:0 auto;"></div>
                    </div>
                </div>
            </div>

            <!-- Ranking Preview -->
            <div class="card mt-xl">
                <h3 class="card-title mb-lg">🏆 Ranking Atual</h3>
                <div id="rankingContainer">
                    <div class="loading-container">
                        <div class="spinner"></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

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

    <!-- Alert Toast -->
    <script src="/assets/js/flags.js?v=202606121841"></script>
    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js?v=202606121841"></script>
    <script src="/assets/js/admin-auth.js?v=202606121841"></script>

    <!-- Change Password Modal -->
    <div id="changePasswordModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h2 class="modal-title">Alterar Senha</h2>
                <button class="modal-close" onclick="closeChangePasswordModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="changePasswordForm">
                    <div class="form-group">
                        <label class="form-label">Nova Senha</label>
                        <input type="password" name="new_password" class="form-input" required minlength="4">
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closeChangePasswordModal()">Cancelar</button>
                <button type="button" class="btn btn-primary"
                    onclick="document.getElementById('changePasswordForm').requestSubmit()">Salvar</button>
            </div>
        </div>
    </div>

    <script>
        const apiBase = '<?= $apiBase ?>';
        const token = getAdminToken();

        function logout() {
            adminLogout();
        }

        async function loadStats() {
            try {
                const [participantsRes, gamesRes, scoresRes] = await Promise.all([
                    fetch(`${apiBase}/participants`),
                    fetch(`${apiBase}/games`),
                    fetch(`${apiBase}/scores`)
                ]);

                const participants = await participantsRes.json();
                const games = await gamesRes.json();
                const scores = await scoresRes.json();

                document.getElementById('participantsCount').textContent = participants.length;
                document.getElementById('gamesCount').textContent = games.length;

                // Count predictions from scores
                const totalPredictions = scores.reduce((sum, p) => sum + (p.games_predicted || 0), 0);
                document.getElementById('predictionsCount').textContent = totalPredictions;

                // Render ranking
                const rankingHtml = scores.length > 0
                    ? `<table class="table">
                        <thead>
                            <tr><th>#</th><th>Participante</th><th>Pontos</th></tr>
                        </thead>
                        <tbody>
                            ${scores.slice(0, 10).map((s, i) => `
                                <tr>
                                    <td>${i + 1}</td>
                                    <td>${s.name}</td>
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
                console.error('Error loading stats:', error);
            }
        }


        // Quick Score - load current/upcoming games
        async function loadQuickScore() {
            try {
                const res = await fetch(`${apiBase}/games`);
                const games = await res.json();
                const now = new Date();

                // Find games that already started (kickoff passed) but have no score yet
                let candidates = games.filter(g => new Date(g.kickoff) <= now && g.score_a === null);

                // Also include games happening today that already have scores (for editing)
                const todayStr = now.toISOString().slice(0, 10);
                const todayGames = games.filter(g => g.kickoff.startsWith(todayStr));

                let displayGames = [];
                if (candidates.length > 0) {
                    displayGames = candidates.slice(-3).reverse();
                } else if (todayGames.length > 0) {
                    displayGames = todayGames.slice(-3).reverse();
                } else {
                    return;
                }

                const card = document.getElementById('quickScoreCard');
                card.style.display = 'block';

                const container = document.getElementById('quickScoreContent');
                container.innerHTML = displayGames.map(game => {
                    const hasScore = game.score_a !== null && game.score_b !== null;
                    return `
                        <div class="quick-score-game" data-game-id="${game.id}">
                            <div class="quick-score-teams">
                                <div class="quick-score-team">
                                    ${getTeamHtml(game.team_a)}
                                    <input type="number" class="quick-score-input" data-side="a" min="0" max="99"
                                        value="${hasScore ? game.score_a : ''}" placeholder="-">
                                </div>
                                <span class="quick-score-vs">×</span>
                                <div class="quick-score-team">
                                    ${getTeamHtml(game.team_b)}
                                    <input type="number" class="quick-score-input" data-side="b" min="0" max="99"
                                        value="${hasScore ? game.score_b : ''}" placeholder="-">
                                </div>
                            </div>
                            <button class="btn btn-primary btn-block quick-score-save" onclick="saveQuickScore(${game.id}, this)">
                                💾 Salvar
                            </button>
                        </div>
                    `;
                }).join('');

            } catch (error) {
                console.error('Error loading quick score:', error);
            }
        }

        async function saveQuickScore(gameId, btn) {
            const gameEl = btn.closest('.quick-score-game');
            const inputA = gameEl.querySelector('[data-side="a"]');
            const inputB = gameEl.querySelector('[data-side="b"]');
            const scoreA = parseInt(inputA.value, 10);
            const scoreB = parseInt(inputB.value, 10);

            if (isNaN(scoreA) || isNaN(scoreB)) {
                showToast('Preencha ambos os placares', 'warning');
                return;
            }

            btn.disabled = true;
            btn.textContent = '⏳ Salvando...';

            try {
                const res = await fetch(`${apiBase}/games/${gameId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ score_a: scoreA, score_b: scoreB })
                });

                if (res.ok) {
                    showToast('✅ Placar atualizado!', 'success');
                    btn.textContent = '✅ Salvo!';
                    setTimeout(() => loadQuickScore(), 1500);
                } else if (res.status === 401) {
                    return;
                } else {
                    showToast('Erro ao atualizar placar', 'error');
                    btn.disabled = false;
                    btn.textContent = '💾 Salvar';
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
                btn.disabled = false;
                btn.textContent = '💾 Salvar';
            }
        }

        loadStats();
        loadQuickScore();

        // Change Password Logic
        const changePasswordModal = document.getElementById('changePasswordModal');

        function openChangePasswordModal() {
            changePasswordModal.classList.add('active');
        }

        function closeChangePasswordModal() {
            changePasswordModal.classList.remove('active');
            document.getElementById('changePasswordForm').reset();
        }

        document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());

            try {
                const res = await fetch(`${apiBase}/change-password`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('Senha alterada com sucesso!', 'success');
                    closeChangePasswordModal();
                } else {
                    showToast('Erro ao alterar senha', 'error');
                }
            } catch (error) {
                console.error(error);
                showToast('Erro de conexão', 'error');
            }
        });

        // Close modal on ESC or overlay click
        changePasswordModal.addEventListener('click', (e) => {
            if (e.target === changePasswordModal) closeChangePasswordModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeChangePasswordModal();
        });

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
                document.getElementById('breakdownLoading').innerHTML = '<div class="text-error" style="text-align: center; padding: 20px;">Erro ao carregar detalhes</div>';
            }
        }

        function closeBreakdownModal() {
            breakdownModal.classList.remove('active');
        }

        breakdownModal.addEventListener('click', (e) => {
            if (e.target === breakdownModal) closeBreakdownModal();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeChangePasswordModal();
                closeBreakdownModal();
            }
        });
    </script>
</body>

</html>
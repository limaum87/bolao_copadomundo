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
    <link rel="stylesheet" href="/assets/css/styles.css">
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
                <a href="/" class="btn btn-secondary btn-sm">← Voltar ao Início</a>
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

            <!-- Backup Section -->
            <div class="card mt-xl">
                <h3 class="card-title mb-lg">💾 Backup do Sistema</h3>
                <div class="form-row">
                    <div>
                        <a href="<?= $apiBase ?>/backup/export" class="btn btn-secondary btn-block" download>
                            📥 Exportar Backup
                        </a>
                        <p class="text-muted mt-sm" style="font-size: 0.875rem;">Download do banco de dados SQLite</p>
                    </div>
                    <div>
                        <form id="importForm" enctype="multipart/form-data">
                            <input type="file" name="file" id="backupFile" accept=".sqlite,.db" style="display: none;">
                            <button type="button" class="btn btn-outline btn-block"
                                onclick="document.getElementById('backupFile').click()">
                                📤 Importar Backup
                            </button>
                            <p class="text-muted mt-sm" style="font-size: 0.875rem;">Restaurar de um arquivo .sqlite</p>
                        </form>
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

    <!-- Alert Toast -->
    <div id="alertToast" class="alert"
        style="position: fixed; bottom: 20px; right: 20px; display: none; max-width: 400px; z-index: 1001;"></div>

    <script>
        const apiBase = '<?= $apiBase ?>';

        function showToast(message, type = 'success') {
            const toast = document.getElementById('alertToast');
            toast.className = `alert alert-${type}`;
            toast.innerHTML = message;
            toast.style.display = 'flex';
            setTimeout(() => toast.style.display = 'none', 3000);
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
                                    <td><strong>${s.total_points || 0}</strong></td>
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

        // Backup import
        document.getElementById('backupFile').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`${apiBase}/backup/import`, {
                    method: 'POST',
                    body: formData
                });

                if (res.ok) {
                    showToast('✅ Backup importado com sucesso!', 'success');
                    loadStats();
                } else {
                    showToast('Erro ao importar backup', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });

        loadStats();
    </script>
</body>

</html>
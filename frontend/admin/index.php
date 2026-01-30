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
    <div id="alertToast" class="alert"
        style="position: fixed; bottom: 20px; right: 20px; display: none; max-width: 400px; z-index: 1001;"></div>

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
        const token = localStorage.getItem('admin_token');

        if (!token) {
            window.location.href = '/admin/login.php';
        }

        function logout() {
            localStorage.removeItem('admin_token');
            window.location.href = '/admin/login.php';
        }

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

        // Backup import
        document.getElementById('backupFile').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`${apiBase}/backup/import`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
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

        // Update export link with token (needs to be handled differently since it's a link)
        // Actually, for download links, we can't easily add headers. 
        // We might need to use fetch and blob, or pass token in query param (less secure but easier).
        // Let's stick to fetch and blob for security.
        document.querySelector('a[href*="/backup/export"]').addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                const res = await fetch(`${apiBase}/backup/export`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = "bolao_backup.sqlite";
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                } else {
                    showToast('Erro ao exportar backup', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
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
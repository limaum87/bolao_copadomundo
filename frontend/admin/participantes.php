<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Participantes - Bolão Copa 2026</title>
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
                    <h1>Participantes</h1>
                    <span class="header-subtitle">Gerencie os participantes do bolão</span>
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
                <a href="/admin/participantes.php" class="active">👥 Participantes</a>
                <a href="/admin/jogos.php">⚽ Jogos</a>
                <a href="/admin/configuracoes.php">⚙️ Configurações</a>
            </nav>

            <!-- Add Participant Form -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">➕ Novo Participante</h3>
                <form id="participantForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Nome *</label>
                            <input type="text" name="name" class="form-input" placeholder="Nome do participante"
                                required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Email (opcional)</label>
                            <input type="email" name="email" class="form-input" placeholder="email@exemplo.com">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">
                        💾 Salvar Participante
                    </button>
                </form>
            </div>

            <!-- Info Alert -->
            <div class="alert alert-success mb-lg">
                💡 <strong>Dica:</strong> Copie o link do participante e envie para que ele possa fazer seus palpites!
            </div>

            <!-- Participants Table -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">👥 Lista de Participantes</h3>
                    <span id="participantsCount" class="badge badge-info"></span>
                </div>
                <div class="table-container">
                    <table class="table" id="participantsTable">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Nome</th>
                                <th>Email</th>
                                <th>Progresso</th>
                                <th>Link de Acesso</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <!-- Predictions Modal -->
    <div id="predictionsModal" class="modal-overlay">
        <div class="modal" style="max-width: 800px;">
            <div class="modal-header">
                <h4 class="modal-title" id="predictionsModalTitle">Palpites do Participante</h4>
                <button type="button" class="modal-close" onclick="closePredictionsModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div id="predictionsList" class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Jogo</th>
                                <th>Palpite</th>
                                <th>Placar Real</th>
                            </tr>
                        </thead>
                        <tbody id="predictionsTableBody"></tbody>
                    </table>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline" onclick="closePredictionsModal()">Fechar</button>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js"></script>

    <script src="/assets/js/flags.js"></script>
    <script>
        const apiBase = '<?= $apiBase ?>';
        const frontendBase = window.location.origin + '/user/';
        const token = localStorage.getItem('admin_token');

        if (!token) {
            window.location.href = '/admin/login.php';
        }

        async function loadParticipants() {
            try {
                const [pRes, gRes, sRes] = await Promise.all([
                    fetch(`${apiBase}/participants`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }),
                    fetch(`${apiBase}/games`),
                    fetch(`${apiBase}/scores`)
                ]);

                const participants = await pRes.json();
                const games = await gRes.json();
                const scores = await sRes.json();

                const totalGames = games.length;

                document.getElementById('participantsCount').textContent = `${participants.length} participantes`;

                const tbody = document.querySelector('#participantsTable tbody');
                tbody.innerHTML = participants.map(p => {
                    const userLink = `${frontendBase}${p.uid}`;
                    const score = scores.find(s => s.id === p.id);
                    const predicted = score ? score.games_predicted : 0;
                    const progressClass = predicted === totalGames ? 'badge-success' : 'badge-warning';

                    return `
                        <tr>
                            <td>${p.id}</td>
                            <td><strong>${p.name}</strong></td>
                            <td>${p.email || '<span class="text-muted">-</span>'}</td>
                            <td>
                                <span class="badge ${progressClass}">
                                    ${predicted} / ${totalGames}
                                </span>
                            </td>
                            <td>
                                <div class="flex gap-sm" style="align-items: center;">
                                    <code style="font-size: 0.75rem; background: var(--color-gray-100); padding: 0.25rem 0.5rem; border-radius: 4px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                        ${userLink}
                                    </code>
                                    <button class="copy-btn" onclick="copyLink('${userLink}', this)">
                                        📋
                                    </button>
                                </div>
                            </td>
                            <td>
                                <div class="flex gap-sm">
                                    <button class="btn btn-sm btn-secondary" onclick="viewPredictions(${p.id}, '${p.uid}', '${p.name}')">
                                        👁️ Palpites
                                    </button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteParticipant(${p.id})">
                                        🗑️
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');

            } catch (error) {
                console.error('Error loading participants:', error);
                showToast('Erro ao carregar participantes', 'error');
            }
        }

        // Predictions Modal
        const predictionsModal = document.getElementById('predictionsModal');

        async function viewPredictions(id, uid, name) {
            document.getElementById('predictionsModalTitle').textContent = `Palpites de ${name}`;
            const tbody = document.getElementById('predictionsTableBody');
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">Carregando...</td></tr>';

            predictionsModal.classList.add('active');

            try {
                const [gRes, pRes] = await Promise.all([
                    fetch(`${apiBase}/games`),
                    fetch(`${apiBase}/predictions?participant_uid=${uid}`)
                ]);

                const games = await gRes.json();
                const predictions = await pRes.json();

                tbody.innerHTML = games.map(game => {
                    const pred = predictions.find(p => p.game_id === game.id);
                    const hasResult = game.score_a !== null && game.score_b !== null;

                    return `
                        <tr>
                            <td style="font-size: 0.875rem;">
                                ${getTeamHtml(game.team_a)} × ${getTeamHtml(game.team_b)}
                            </td>
                            <td>
                                ${pred
                            ? `<strong>${pred.goals_a} × ${pred.goals_b}</strong>`
                            : '<span class="text-muted italic">Sem palpite</span>'}
                            </td>
                            <td>
                                ${hasResult
                            ? `<span class="badge badge-info">${game.score_a} × ${game.score_b}</span>`
                            : '<span class="text-muted">-</span>'}
                            </td>
                        </tr>
                    `;
                }).join('');

            } catch (error) {
                console.error(error);
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-error">Erro ao carregar palpites</td></tr>';
            }
        }

        function closePredictionsModal() {
            predictionsModal.classList.remove('active');
        }

        // Close modal on ESC or overlay click
        predictionsModal.addEventListener('click', (e) => {
            if (e.target === predictionsModal) closePredictionsModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closePredictionsModal();
        });

        function copyLink(link, btn) {
            // Função auxiliar para feedback visual
            function onSuccess() {
                btn.classList.add('copied');
                btn.textContent = '✅ Copiado!';
                showToast('📋 Link copiado!', 'success');
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.textContent = '📋 Copiar';
                }, 2000);
            }

            function onError() {
                showToast('Erro ao copiar', 'error');
            }

            // Tenta usar a API moderna do clipboard (requer HTTPS)
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(link).then(onSuccess).catch(onError);
            } else {
                // Fallback para ambientes HTTP usando execCommand
                try {
                    const textArea = document.createElement('textarea');
                    textArea.value = link;
                    textArea.style.position = 'fixed';
                    textArea.style.left = '-9999px';
                    textArea.style.top = '-9999px';
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    const successful = document.execCommand('copy');
                    document.body.removeChild(textArea);
                    if (successful) {
                        onSuccess();
                    } else {
                        onError();
                    }
                } catch (err) {
                    onError();
                }
            }
        }

        // Add new participant
        document.getElementById('participantForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {
                name: formData.get('name'),
                email: formData.get('email') || null
            };

            try {
                const res = await fetch(`${apiBase}/participants`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('✅ Participante adicionado!', 'success');
                    e.target.reset();
                    loadParticipants();
                } else {
                    showToast('Erro ao salvar participante', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });

        // Delete participant
        async function deleteParticipant(id) {
            if (!confirm('Tem certeza que deseja remover este participante? Todos os palpites serão perdidos.')) return;

            try {
                await fetch(`${apiBase}/participants/${id}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                showToast('🗑️ Participante removido', 'success');
                loadParticipants();
            } catch (error) {
                showToast('Erro ao remover participante', 'error');
            }
        }

        loadParticipants();
    </script>
</body>

</html>
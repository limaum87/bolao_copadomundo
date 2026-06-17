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
    <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Bolão Copa">
    <meta name="mobile-web-app-capable" content="yes">
    <script src="/assets/js/pwa-register.js?v=202606141800" defer></script>
    <title>Configurações - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606171200">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div>
                    <h1>Configurações</h1>
                    <span class="header-subtitle">Regras de pontuação do bolão</span>
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
                <a href="/admin/jogos.php">⚽ Jogos</a>
                <a href="/admin/configuracoes.php" class="active">⚙️ Configurações</a>
            </nav>

            <!-- Game Scoring Config -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">⚽ Pontuação por Jogo</h3>
                <p class="text-muted mb-lg">Defina quantos pontos cada tipo de acerto vale na previsão de jogos.</p>
                <form id="gameScoringForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">🎯 Placar Exato</label>
                            <input type="number" name="exact_score" class="form-input" min="0" required>
                            <small class="text-muted">Acertou o placar dos dois times</small>
                        </div>
                        <div class="form-group">
                            <label class="form-label">✅ Resultado Correto</label>
                            <input type="number" name="correct_result" class="form-input" min="0" required>
                            <small class="text-muted">Acertou vencedor ou empate, mas errou o placar</small>
                        </div>
                        <div class="form-group">
                            <label class="form-label">🔵 Placar Parcial</label>
                            <input type="number" name="partial_score" class="form-input" min="0" required>
                            <small class="text-muted">Acertou os gols de um dos times</small>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Finals Scoring Config -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">🏆 Pontuação das Finais</h3>
                <p class="text-muted mb-lg">Defina quantos pontos cada posição vale na previsão de classificação final.</p>
                <form id="finalsScoringForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">🥇 Campeão</label>
                            <input type="number" name="champion" class="form-input" min="0" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">🥈 Vice-campeão</label>
                            <input type="number" name="runner_up" class="form-input" min="0" required>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">🥉 3º Lugar</label>
                            <input type="number" name="third_place" class="form-input" min="0" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">4️⃣ 4º Lugar</label>
                            <input type="number" name="fourth_place" class="form-input" min="0" required>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Notifications Config -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">🔔 Notificações</h3>
                <p class="text-muted mb-lg">Defina o horário do lembrete diário enviado aos participantes com notificação ativa que ainda não completaram os palpites dos jogos do dia.</p>
                <form id="notificationsForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">⏰ Hora do lembrete diário</label>
                            <select name="daily_reminder_hour" class="form-input" required>
                            </select>
                            <small class="text-muted">A partir dessa hora, o servidor dispara 1x/dia o aviso (horário de Brasília)</small>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Finals Deadline -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">⏰ Prazo para Palpites Finais</h3>
                <p class="text-muted mb-lg">Defina até quando os participantes podem enviar seus palpites de classificação final (campeão, vice, etc.). Deixe vazio para sem prazo.</p>
                <form id="finalsDeadlineForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">📅 Data/Hora Limite</label>
                            <input type="datetime-local" name="finals_deadline" class="form-input">
                            <small class="text-muted">Quando expirar, os palpites finais ficam bloqueados para todos</small>
                        </div>
                    </div>
                </form>
            </div>

            <!-- Tournament Outcome -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">🏆 Resultado Final do Torneio</h3>
                <p class="text-muted mb-lg">Defina os 4 primeiros lugares para calcular os pontos das previsões de classificação.</p>
                <form id="tournamentOutcomeForm">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">🥇 Campeão</label>
                            <select name="champion" class="form-input"></select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">🥈 Vice-campeão</label>
                            <select name="runner_up" class="form-input"></select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">🥉 3º Lugar</label>
                            <select name="third_place" class="form-input"></select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">4️⃣ 4º Lugar</label>
                            <select name="fourth_place" class="form-input"></select>
                        </div>
                    </div>
                    <div style="text-align: right; margin-top: var(--space-md);">
                        <button type="button" class="btn btn-secondary" onclick="saveOutcome()">💾 Salvar Resultado Final</button>
                    </div>
                </form>
            </div>

            <!-- Migration Section -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">🔧 Correção de Horários (Migration)</h3>
                <p class="text-muted mb-md">Corrige os horários de 7 jogos que estavam divergentes do site oficial da FIFA.</p>
                <button type="button" class="btn btn-primary" onclick="fixKickoffs()">
                    ✅ Aplicar Correção de Horários
                </button>
            </div>

            <!-- Backup Section -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">💾 Backup do Sistema</h3>
                <div class="form-row">
                    <div>
                        <button type="button" class="btn btn-secondary btn-block" onclick="exportBackup()">
                            📥 Exportar Backup
                        </button>
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

            <!-- Ranking History (backfill) -->
            <div class="card mb-xl">
                <h3 class="card-title mb-lg">📈 Histórico do Ranking</h3>
                <p class="text-muted mb-md" style="font-size: 0.9rem;">
                    Recria o histórico de posições do ranking a partir dos jogos já
                    finalizados (um snapshot por dia de jogo). Isso dá uma base real
                    para a coluna de variação (▲/▼) funcionar desde o início do torneio.
                </p>
                <button type="button" class="btn btn-secondary btn-block" onclick="backfillRanking()">
                    🔄 Recriar Histórico do Ranking
                </button>
                <p class="text-muted mt-sm" style="font-size: 0.8rem;">
                    Seguro e idempotente: pode ser executado quantas vezes quiser.
                </p>
                <div id="backfillResult" style="display:none;" class="mt-md"></div>
            </div>

            <!-- Save Button -->
            <div class="card">
                <div class="form-row" style="justify-content: flex-end;">
                    <button type="button" class="btn btn-outline btn-lg" onclick="resetDefaults()">
                        🔄 Restaurar Padrão
                    </button>
                    <button type="button" class="btn btn-primary btn-lg" onclick="saveConfig()">
                        💾 Salvar Configurações
                    </button>
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

        const DEFAULTS = {
            exact_score: 10,
            correct_result: 5,
            partial_score: 2,
            champion: 50,
            runner_up: 15,
            third_place: 10,
            fourth_place: 10,
            daily_reminder_hour: 11,
        };

        // Popula o select de hora do lembrete diário (00–23)
        (function populateReminderHour() {
            const sel = document.querySelector('select[name="daily_reminder_hour"]');
            if (!sel) return;
            let opts = '';
            for (let h = 0; h <= 23; h++) {
                const hh = String(h).padStart(2, '0');
                opts += `<option value="${h}">${hh}:00</option>`;
            }
            sel.innerHTML = opts;
        })();

        function fillForm(config) {
            const fields = ['exact_score', 'correct_result', 'partial_score',
                            'champion', 'runner_up', 'third_place', 'fourth_place'];
            fields.forEach(field => {
                const input = document.querySelector(`input[name="${field}"]`);
                if (input) {
                    input.value = config[field];
                }
            });

            // Fill finals deadline
            const deadlineInput = document.querySelector('input[name="finals_deadline"]');
            if (deadlineInput && config.finals_deadline) {
                // Convert ISO to datetime-local format (YYYY-MM-DDTHH:MM)
                const d = new Date(config.finals_deadline);
                const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
                deadlineInput.value = local.toISOString().slice(0, 16);
            }

            // Fill daily reminder hour
            const reminderSelect = document.querySelector('select[name="daily_reminder_hour"]');
            if (reminderSelect) {
                reminderSelect.value = String(config.daily_reminder_hour ?? DEFAULTS.daily_reminder_hour);
            }
        }

        function getFormData() {
            const fields = ['exact_score', 'correct_result', 'partial_score',
                            'champion', 'runner_up', 'third_place', 'fourth_place'];
            const data = {};
            fields.forEach(field => {
                const input = document.querySelector(`input[name="${field}"]`);
                if (input) {
                    data[field] = parseInt(input.value, 10);
                }
            });

            // Include finals deadline
            const deadlineInput = document.querySelector('input[name="finals_deadline"]');
            if (deadlineInput) {
                data.finals_deadline = deadlineInput.value || null;
            }

            // Include daily reminder hour
            const reminderSelect = document.querySelector('select[name="daily_reminder_hour"]');
            if (reminderSelect) {
                data.daily_reminder_hour = parseInt(reminderSelect.value, 10);
            }

            return data;
        }

        function populateOutcomeSelects() {
            const teams = Object.keys(countryCodes).sort((a, b) => a.localeCompare(b, 'pt-BR'));
            const selects = document.querySelectorAll('#tournamentOutcomeForm select');
            selects.forEach(select => {
                select.innerHTML = '<option value="">Selecione...</option>' +
                    teams.map(t => `<option value="${t}">${t}</option>`).join('');
            });
        }
        populateOutcomeSelects();

        async function loadOutcome() {
            try {
                const res = await fetch(`${apiBase}/tournament_outcome`);
                if (res.ok) {
                    const data = await res.json();
                    ['champion', 'runner_up', 'third_place', 'fourth_place'].forEach(field => {
                        const select = document.querySelector(`#tournamentOutcomeForm [name="${field}"]`);
                        if (select && data[field]) select.value = data[field];
                    });
                }
            } catch (error) {
                console.error('Error loading tournament outcome:', error);
            }
        }

        async function saveOutcome() {
            const fields = ['champion', 'runner_up', 'third_place', 'fourth_place'];
            const data = {};
            for (const field of fields) {
                const select = document.querySelector(`#tournamentOutcomeForm [name="${field}"]`);
                data[field] = select.value || null;
            }

            try {
                const res = await fetch(`${apiBase}/tournament_outcome`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('Resultado final salvo com sucesso!', 'success');
                } else if (res.status === 401) {
                    // 401 já é tratado automaticamente pelo admin-auth.js
                    return;
                } else {
                    showToast('Erro ao salvar resultado final.', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão.', 'error');
            }
        }

        async function loadConfig() {
            try {
                const res = await fetch(`${apiBase}/scoring_config`);
                if (res.ok) {
                    const config = await res.json();
                    fillForm(config);
                } else {
                    fillForm(DEFAULTS);
                }
            } catch (error) {
                console.error('Error loading scoring config:', error);
                fillForm(DEFAULTS);
            }
        }

        async function saveConfig() {
            const data = getFormData();

            // Validate all values are non-negative integers
            for (const [key, value] of Object.entries(data)) {
                if (key === 'finals_deadline') continue; // pode ser null/string
                if (key === 'daily_reminder_hour') {
                    if (isNaN(value) || value < 0 || value > 23) {
                        showToast('A hora do lembrete deve estar entre 0 e 23.', 'error');
                        return;
                    }
                    continue;
                }
                if (isNaN(value) || value < 0) {
                    showToast('Todos os valores devem ser números inteiros não negativos.', 'error');
                    return;
                }
            }

            try {
                const res = await fetch(`${apiBase}/scoring_config`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    showToast('Configurações salvas com sucesso!', 'success');
                } else if (res.status === 401) {
                    // 401 já é tratado automaticamente pelo admin-auth.js
                    return;
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Erro ao salvar configurações.', 'error');
                }
            } catch (error) {
                console.error('Error saving config:', error);
                showToast('Erro de conexão.', 'error');
            }
        }

        function resetDefaults() {
            if (confirm('Restaurar os valores padrão de pontuação?')) {
                fillForm(DEFAULTS);
                showToast('Valores padrão restaurados. Clique em Salvar para confirmar.', 'success');
            }
        }

        loadConfig();
        loadOutcome();

        // Fix Kickoffs
        async function fixKickoffs() {
            if (!confirm('\u26a0\ufe0f Deseja aplicar a corre\u00e7\u00e3o de hor\u00e1rios dos jogos conforme site da FIFA?\n\nIsso atualizar\u00e1 o hor\u00e1rio de 7 jogos.')) return;

            try {
                const res = await fetch(`${apiBase}/games/fix-kickoffs`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (res.ok) {
                    const data = await res.json();
                    const msg = data.updated.length > 0
                        ? `\u2705 ${data.updated.length} jogo(s) corrigido(s)! ${data.skipped.length} j\u00e1 estavam corretos.`
                        : '\u2139\ufe0f Todos os hor\u00e1rios j\u00e1 estavam corretos.';
                    showToast(msg, 'success');
                } else if (res.status === 401) {
                    return;
                } else {
                    showToast('Erro ao aplicar corre\u00e7\u00e3o', 'error');
                }
            } catch (error) {
                showToast('Erro de conex\u00e3o', 'error');
            }
        }

        // Ranking History Backfill
        async function backfillRanking() {
            if (!confirm('Isso vai recriar todo o histórico do ranking a partir dos jogos finalizados. Continuar?')) {
                return;
            }
            const resultDiv = document.getElementById('backfillResult');
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = '<div class="alert alert-info">⏳ Recriando histórico...</div>';
            try {
                const res = await fetch(`${apiBase}/ranking/backfill`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    let html = `<div class="alert alert-success">✅ Histórico recriado: <strong>${data.rebuilt_dates} dia(s)</strong> de jogo.</div>`;
                    if (data.summary && data.summary.length) {
                        html += '<div class="table-container mt-md"><table class="table"><thead><tr><th>Data</th><th>Jogos</th><th>Top 3 do dia</th></tr></thead><tbody>';
                        data.summary.forEach(s => {
                            const top3 = s.top3.map(t => `${t.position}º ${t.name} (${t.points})`).join(' · ');
                            html += `<tr><td>${s.date}</td><td>${s.games_counted}</td><td style="font-size:0.85rem;">${top3}</td></tr>`;
                        });
                        html += '</tbody></table></div>';
                    }
                    resultDiv.innerHTML = html;
                    showToast('✅ Histórico do ranking recriado!', 'success');
                } else if (res.status === 401) {
                    return;
                } else {
                    resultDiv.innerHTML = '<div class="alert alert-error">Erro ao recriar histórico</div>';
                    showToast('Erro ao recriar histórico', 'error');
                }
            } catch (error) {
                resultDiv.innerHTML = '<div class="alert alert-error">Erro de conexão</div>';
                showToast('Erro de conexão', 'error');
            }
        }

        // Backup Export
        async function exportBackup() {
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
                    showToast('✅ Backup exportado!', 'success');
                } else {
                    showToast('Erro ao exportar backup', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        }

        // Backup Import
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
                } else {
                    showToast('Erro ao importar backup', 'error');
                }
            } catch (error) {
                showToast('Erro de conexão', 'error');
            }
        });
    </script>
</body>

</html>

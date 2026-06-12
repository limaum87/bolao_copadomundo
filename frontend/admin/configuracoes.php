<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configurações - Bolão Copa 2026</title>
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
    <script src="/assets/js/toast.js"></script>
    <script src="/assets/js/admin-auth.js"></script>

    <script src="/assets/js/flags.js"></script>
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
        };

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
    </script>
</body>

</html>

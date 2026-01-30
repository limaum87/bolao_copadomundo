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
    <link rel="stylesheet" href="/assets/css/styles.css">
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

    <!-- Alert Toast -->
    <div id="alertToast" class="alert"
        style="position: fixed; bottom: 20px; right: 20px; display: none; max-width: 400px; z-index: 1001;"></div>

    <script>
        const apiBase = '<?= $apiBase ?>';
        const token = localStorage.getItem('admin_token');

        if (!token) {
            window.location.href = '/admin/login.php';
        }

        const DEFAULTS = {
            exact_score: 10,
            correct_result: 5,
            partial_score: 2,
            champion: 50,
            runner_up: 15,
            third_place: 10,
            fourth_place: 10,
        };

        function showToast(message, type = 'success') {
            const toast = document.getElementById('alertToast');
            toast.className = `alert alert-${type}`;
            toast.innerHTML = message;
            toast.style.display = 'flex';
            setTimeout(() => toast.style.display = 'none', 3000);
        }

        function fillForm(config) {
            const fields = ['exact_score', 'correct_result', 'partial_score',
                            'champion', 'runner_up', 'third_place', 'fourth_place'];
            fields.forEach(field => {
                const input = document.querySelector(`input[name="${field}"]`);
                if (input) {
                    input.value = config[field];
                }
            });
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
            return data;
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
                    showToast('Sessão expirada. Faça login novamente.', 'error');
                    setTimeout(() => window.location.href = '/admin/login.php', 1500);
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
    </script>
</body>

</html>

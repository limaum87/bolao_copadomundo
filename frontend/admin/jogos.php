<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Admin | Jogos</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; }
        table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
        th, td { border: 1px solid #ddd; padding: 0.5rem; }
        form { margin-top: 1rem; }
        label { display: block; margin: 0.25rem 0; }
    </style>
</head>
<body>
<h1>Gerenciar Jogos</h1>
<a href="/frontend/admin/index.php">Voltar</a>
<section>
    <h3>Novo jogo</h3>
    <form id="gameForm">
        <label>Data/hora (ISO ex: 2026-06-11T16:00:00)<br><input type="text" name="kickoff" required></label>
        <label>Time A <br><input type="text" name="team_a" required></label>
        <label>Time B <br><input type="text" name="team_b" required></label>
        <button type="submit">Salvar</button>
    </form>
</section>
<section>
    <h3>Lista de jogos</h3>
    <table id="gamesTable">
        <thead>
        <tr><th>ID</th><th>Início</th><th>Times</th><th>Placar</th><th>Ações</th></tr>
        </thead>
        <tbody></tbody>
    </table>
</section>
<script>
    const apiBase = '<?= $apiBase ?>';

    async function loadGames() {
        const res = await fetch(`${apiBase}/games`);
        const games = await res.json();
        const body = document.querySelector('#gamesTable tbody');
        body.innerHTML = '';
        games.forEach(game => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${game.id}</td>
                <td>${game.kickoff}</td>
                <td>${game.team_a} x ${game.team_b}</td>
                <td>${game.score_a ?? '-'} x ${game.score_b ?? '-'}</td>
                <td>
                    <button data-id="${game.id}" class="delete">Apagar</button>
                    <button data-id="${game.id}" class="result">Atualizar placar</button>
                </td>`;
            body.appendChild(row);
        });
    }

    document.querySelector('#gameForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        const res = await fetch(`${apiBase}/games`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (res.ok) {
            e.target.reset();
            loadGames();
        } else {
            alert('Erro ao salvar jogo');
        }
    });

    document.querySelector('#gamesTable').addEventListener('click', async (e) => {
        if (e.target.classList.contains('delete')) {
            const id = e.target.dataset.id;
            await fetch(`${apiBase}/games/${id}`, { method: 'DELETE' });
            loadGames();
        }
        if (e.target.classList.contains('result')) {
            const id = e.target.dataset.id;
            const scoreA = prompt('Gols do time A:');
            const scoreB = prompt('Gols do time B:');
            await fetch(`${apiBase}/games/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({score_a: parseInt(scoreA, 10), score_b: parseInt(scoreB, 10)})
            });
            loadGames();
        }
    });

    loadGames();
</script>
</body>
</html>

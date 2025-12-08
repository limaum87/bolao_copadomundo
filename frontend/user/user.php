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
    <title>Meus palpites</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; }
        table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
        th, td { border: 1px solid #ddd; padding: 0.5rem; }
        label { display: block; margin: 0.25rem 0; }
        .finals { margin-top: 1rem; padding: 1rem; border: 1px solid #ccc; }
    </style>
</head>
<body>
<h1>Palpites do participante <?= htmlspecialchars($uid) ?></h1>
<section>
    <h3>Jogos</h3>
    <table id="gamesTable">
        <thead>
        <tr><th>Início</th><th>Jogo</th><th>Meu palpite</th><th>Ações</th></tr>
        </thead>
        <tbody></tbody>
    </table>
</section>
<section class="finals">
    <h3>Palpite Final</h3>
    <form id="finalsForm">
        <input type="hidden" name="participant_uid" value="<?= $uid ?>">
        <label>Campeão <input type="text" name="champion" required></label>
        <label>Vice <input type="text" name="runner_up" required></label>
        <label>3º lugar <input type="text" name="third_place" required></label>
        <label>4º lugar <input type="text" name="fourth_place" required></label>
        <button type="submit">Salvar palpite final</button>
    </form>
</section>
<script>
    const apiBase = '<?= $apiBase ?>';
    const uid = '<?= $uid ?>';

    async function loadData() {
        const [gamesRes, predRes, finalsRes] = await Promise.all([
            fetch(`${apiBase}/games`),
            fetch(`${apiBase}/predictions?participant_uid=${uid}`),
            fetch(`${apiBase}/finals_predictions?participant_uid=${uid}`)
        ]);
        const games = await gamesRes.json();
        const preds = await predRes.json();
        const finals = await finalsRes.json();
        const myFinals = finals[0];

        const body = document.querySelector('#gamesTable tbody');
        body.innerHTML = '';
        games.forEach(game => {
            const myPred = preds.find(p => p.game_id === game.id);
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${game.kickoff}</td>
                <td>${game.team_a} x ${game.team_b}</td>
                <td>${myPred ? `${myPred.goals_a} x ${myPred.goals_b}` : '-'}</td>
                <td><button data-id="${game.id}" class="predict">Palpitar/editar</button></td>`;
            body.appendChild(row);
        });

        if (myFinals) {
            ['champion','runner_up','third_place','fourth_place'].forEach(field => {
                const input = document.querySelector(`#finalsForm [name=${field}]`);
                if (input && myFinals[field]) input.value = myFinals[field];
            });
        }
    }

    document.querySelector('#gamesTable').addEventListener('click', async (e) => {
        if (!e.target.classList.contains('predict')) return;
        const gameId = e.target.dataset.id;
        const goalsA = prompt('Gols do time A:');
        const goalsB = prompt('Gols do time B:');
        const res = await fetch(`${apiBase}/predictions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ participant_uid: uid, game_id: parseInt(gameId, 10), goals_a: parseInt(goalsA, 10), goals_b: parseInt(goalsB, 10) })
        });
        if (!res.ok) {
            const msg = await res.json();
            alert(msg.error || 'Erro ao salvar palpite');
        }
        loadData();
    });

    document.querySelector('#finalsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        const res = await fetch(`${apiBase}/finals_predictions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (res.ok) {
            alert('Palpite final salvo');
        } else {
            alert('Erro ao salvar palpite final');
        }
    });

    loadData();
</script>
</body>
</html>

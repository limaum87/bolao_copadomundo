<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Admin | Participantes</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; }
        table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
        th, td { border: 1px solid #ddd; padding: 0.5rem; }
        form { margin-top: 1rem; }
        label { display: block; margin: 0.25rem 0; }
    </style>
</head>
<body>
<h1>Participantes</h1>
<a href="/frontend/admin/index.php">Voltar</a>
<section>
    <h3>Novo participante</h3>
    <form id="participantForm">
        <label>Nome <br><input type="text" name="name" required></label>
        <label>Email (opcional) <br><input type="email" name="email"></label>
        <button type="submit">Salvar</button>
    </form>
</section>
<section>
    <h3>Lista</h3>
    <table id="participantsTable">
        <thead>
        <tr><th>ID</th><th>Nome</th><th>Email</th><th>UID</th><th>Ações</th></tr>
        </thead>
        <tbody></tbody>
    </table>
</section>
<script>
    const apiBase = '<?= $apiBase ?>';

    async function loadParticipants() {
        const res = await fetch(`${apiBase}/participants`);
        const items = await res.json();
        const body = document.querySelector('#participantsTable tbody');
        body.innerHTML = '';
        items.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.id}</td>
                <td>${item.name}</td>
                <td>${item.email ?? ''}</td>
                <td><code>${item.uid}</code></td>
                <td><button data-id="${item.id}" class="delete">Apagar</button></td>`;
            body.appendChild(row);
        });
    }

    document.querySelector('#participantForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        const res = await fetch(`${apiBase}/participants`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (res.ok) {
            e.target.reset();
            loadParticipants();
        } else {
            alert('Erro ao salvar participante');
        }
    });

    document.querySelector('#participantsTable').addEventListener('click', async (e) => {
        if (e.target.classList.contains('delete')) {
            const id = e.target.dataset.id;
            await fetch(`${apiBase}/participants/${id}`, { method: 'DELETE' });
            loadParticipants();
        }
    });

    loadParticipants();
</script>
</body>
</html>

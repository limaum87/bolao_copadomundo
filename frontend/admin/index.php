<?php
require_once __DIR__ . '/../config.php';
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Admin | Bolão 2026</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; }
        a { display: inline-block; margin-right: 1rem; }
        .card { border: 1px solid #ddd; padding: 1rem; margin-bottom: 1rem; border-radius: 4px; }
    </style>
</head>
<body>
<h1>Admin - Bolão da Copa 2026</h1>
<div class="card">
    <h3>Atalhos</h3>
    <a href="/frontend/admin/jogos.php">Gerenciar jogos</a>
    <a href="/frontend/admin/participantes.php">Gerenciar participantes</a>
</div>
<div class="card">
    <h3>Backup</h3>
    <form id="exportForm" method="get" action="<?= $apiBase ?>/backup/export">
        <button type="submit">Exportar banco (SQLite)</button>
    </form>
    <form id="importForm" method="post" action="<?= $apiBase ?>/backup/import" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Importar backup</button>
    </form>
</div>
</body>
</html>

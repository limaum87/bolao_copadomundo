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
    <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png?v=2">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Bolão Copa">
    <meta name="mobile-web-app-capable" content="yes">
    <script src="/assets/js/pwa-register.js?v=202606141800" defer></script>
    <title>Login Admin - Bolão Copa 2026</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606171200">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.css">
    <style>
        .login-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--color-gray-100);
            padding: var(--space-md);
        }

        .login-card {
            background: white;
            padding: var(--space-2xl);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            width: 100%;
            max-width: 400px;
        }

        .login-title {
            text-align: center;
            margin-bottom: var(--space-xl);
            color: var(--color-dark);
        }
    </style>
</head>

<body>
    <div class="login-container">
        <div class="login-card">
            <h1 class="login-title">Área Administrativa</h1>
            <form id="loginForm">
                <div class="form-group">
                    <label class="form-label">Usuário</label>
                    <input type="text" name="username" class="form-input" required autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Senha</label>
                    <input type="password" name="password" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary btn-full">Entrar</button>
            </form>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/toastify-js@1.12.0/src/toastify.min.js"></script>
    <script src="/assets/js/toast.js?v=202606121643"></script>
    <script>
        const apiBase = '<?= $apiBase ?>';

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());

            try {
                const res = await fetch(`${apiBase}/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (res.ok) {
                    const result = await res.json();
                    localStorage.setItem('admin_token', result.token);
                    window.location.href = '/admin/';
                } else {
                    showToast('Usuário ou senha incorretos', 'error');
                }
            } catch (error) {
                console.error(error);
                showToast('Erro ao conectar com o servidor', 'error');
            }
        });
    </script>
</body>

</html>
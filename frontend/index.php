<?php
require_once __DIR__ . '/config.php';
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
    <!-- PWA: se aberto como app instalado e já sabemos o perfil do participante,
         redireciona direto para o perfil em vez de mostrar a landing page. -->
    <script>
    (function () {
        try {
            var standalone = window.matchMedia('(display-mode: standalone)').matches
                || window.navigator.standalone === true;
            if (!standalone) return;
            var uid = localStorage.getItem('bolao_uid');
            if (!uid) {
                var m = document.cookie.match(/(?:^|;\s*)bolao_uid=([A-Za-z0-9]{6,128})/);
                if (m) uid = m[1];
            }
            if (uid) location.replace('/user/' + encodeURIComponent(uid));
        } catch (e) {}
    })();
    </script>
    <link rel="icon" href="/assets/img/favicon.ico" sizes="any">
    <link rel="icon" href="/assets/img/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Bolão Copa">
    <meta name="mobile-web-app-capable" content="yes">
    <script src="/assets/js/pwa-register.js?v=202606141800" defer></script>
    <title>Bolão Copa do Mundo 2026 🏆</title>
    <meta name="description"
        content="Participe do bolão da Copa do Mundo 2026! Faça seus palpites e concorra a prêmios.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/css/styles.css?v=202606161600">
    <style>
        /* Landing page specific styles */
        .landing-hero {
            background: linear-gradient(135deg, #009739 0%, #007a2e 50%, #002776 100%);
            min-height: 70vh;
            display: flex;
            align-items: center;
            position: relative;
            overflow: hidden;
        }

        .landing-hero::before {
            content: '';
            position: absolute;
            top: -200px;
            right: -200px;
            width: 600px;
            height: 600px;
            background: #FEDD00;
            border-radius: 50%;
            opacity: 0.15;
            animation: float 6s ease-in-out infinite;
        }

        .landing-hero::after {
            content: '';
            position: absolute;
            bottom: -150px;
            left: -150px;
            width: 400px;
            height: 400px;
            background: #002776;
            border-radius: 50%;
            opacity: 0.2;
            animation: float 8s ease-in-out infinite reverse;
        }

        @keyframes float {

            0%,
            100% {
                transform: translateY(0px);
            }

            50% {
                transform: translateY(-30px);
            }
        }

        .hero-inner {
            position: relative;
            z-index: 1;
            text-align: center;
            color: white;
            padding: var(--space-2xl) 0;
        }

        .hero-emoji {
            font-size: 6rem;
            display: block;
            margin-bottom: var(--space-lg);
            animation: bounce 2s ease-in-out infinite;
        }

        @keyframes bounce {

            0%,
            100% {
                transform: translateY(0);
            }

            50% {
                transform: translateY(-10px);
            }
        }

        .hero-title {
            font-size: clamp(2.5rem, 6vw, 4rem);
            font-weight: 800;
            margin-bottom: var(--space-md);
            text-shadow: 2px 4px 8px rgba(0, 0, 0, 0.3);
        }

        .hero-title span {
            color: #FEDD00;
        }

        .hero-subtitle {
            font-size: clamp(1rem, 2.5vw, 1.5rem);
            opacity: 0.9;
            margin-bottom: var(--space-xl);
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }

        .hero-buttons {
            display: flex;
            gap: var(--space-md);
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn-hero {
            padding: var(--space-md) var(--space-2xl);
            font-size: var(--font-size-lg);
            border-radius: var(--radius-xl);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .features-section {
            padding: var(--space-3xl) 0;
            background: white;
        }

        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: var(--space-xl);
        }

        .feature-card {
            text-align: center;
            padding: var(--space-xl);
            border-radius: var(--radius-xl);
            background: var(--color-gray-100);
            transition: all var(--transition-normal);
        }

        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-lg);
            background: white;
        }

        .feature-icon {
            font-size: 4rem;
            margin-bottom: var(--space-md);
        }

        .feature-title {
            font-size: var(--font-size-xl);
            margin-bottom: var(--space-sm);
            color: var(--color-dark);
        }

        .feature-text {
            color: var(--color-gray-700);
        }

        .scoring-section {
            padding: var(--space-3xl) 0;
            background: linear-gradient(135deg, var(--color-blue) 0%, var(--color-blue-dark) 100%);
            color: white;
        }

        .scoring-title {
            text-align: center;
            color: var(--color-yellow);
            margin-bottom: var(--space-2xl);
        }

        .scoring-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: var(--space-lg);
        }

        .scoring-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-lg);
            padding: var(--space-lg);
            text-align: center;
            backdrop-filter: blur(10px);
        }

        .scoring-points {
            font-size: var(--font-size-4xl);
            font-weight: 800;
            color: var(--color-yellow);
        }

        .scoring-label {
            font-size: var(--font-size-sm);
            opacity: 0.9;
            margin-top: var(--space-xs);
        }

        .footer {
            background: var(--color-dark);
            color: white;
            padding: var(--space-xl) 0;
            text-align: center;
        }

        .footer a {
            color: var(--color-yellow);
        }
    </style>
</head>

<body>
    <!-- Hero Section -->
    <section class="landing-hero">
        <div class="container">
            <div class="hero-inner">
                <span class="hero-emoji">⚽🏆</span>
                <h1 class="hero-title">Bolão <span>Copa 2026</span></h1>
                <p class="hero-subtitle">
                    Faça seus palpites para todos os jogos da Copa do Mundo e concorra a prêmios incríveis!
                </p>
                <!-- Admin button removed -->
            </div>
        </div>
    </section>

    <!-- Features Section -->
    <section class="features-section">
        <div class="container">
            <h2 class="text-center mb-xl">Como Funciona</h2>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">🔗</div>
                    <h3 class="feature-title">Link Exclusivo</h3>
                    <p class="feature-text">
                        Você recebe um link único e secreto. Sem senha, sem cadastro complicado!
                    </p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🎯</div>
                    <h3 class="feature-title">Faça Seus Palpites</h3>
                    <p class="feature-text">
                        Palpite em todos os jogos da Copa até o início de cada partida.
                    </p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🏆</div>
                    <h3 class="feature-title">Acerte e Ganhe</h3>
                    <p class="feature-text">
                        Quanto mais acertos, mais pontos! Disputa acirrada até a final.
                    </p>
                </div>
            </div>
        </div>
    </section>

    <!-- Scoring Section -->
    <section class="scoring-section">
        <div class="container">
            <h2 class="scoring-title">📊 Regras de Pontuação</h2>
            <div class="scoring-grid">
                <div class="scoring-card">
                    <div class="scoring-points">10</div>
                    <div class="scoring-label">Placar exato</div>
                </div>
                <div class="scoring-card">
                    <div class="scoring-points">5</div>
                    <div class="scoring-label">Vencedor + saldo</div>
                </div>
                <div class="scoring-card">
                    <div class="scoring-points">2</div>
                    <div class="scoring-label">Apenas vencedor</div>
                </div>
                <div class="scoring-card">
                    <div class="scoring-points">50</div>
                    <div class="scoring-label">🥇 Campeão</div>
                </div>
                <div class="scoring-card">
                    <div class="scoring-points">15</div>
                    <div class="scoring-label">🥈 Vice</div>
                </div>
                <div class="scoring-card">
                    <div class="scoring-points">10</div>
                    <div class="scoring-label">🥉 3º e 4º</div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <p>⚽ Bolão Copa do Mundo 2026 • Boa sorte a todos! 🇧🇷</p>
            <p class="mt-sm text-muted" style="opacity: 0.7;">
                <a href="/admin/">Área Administrativa</a>
            </p>
        </div>
    </footer>
</body>

</html>
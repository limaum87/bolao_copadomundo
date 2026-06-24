<?php
// Manifest dinâmico do PWA.
//
// O start_url é definido para o perfil do participante (/user/<uid>) quando
// existe um cookie "bolao_uid" (gravado ao visitar /user/<uid>). Assim, ao
// instalar o app a partir do próprio link do participante, o ícone abre
// direto no perfil dele — inclusive no iOS, que congela o start_url.
//
// Servido de forma transparente no URL /manifest.webmanifest via rewrite
// no .htaccess (mantém o id="/" estável para atualizações do app).

header('Content-Type: application/manifest+json; charset=utf-8');
header('Cache-Control: no-cache, must-revalidate');

$uid = '';
if (!empty($_COOKIE['bolao_uid']) && preg_match('/^[A-Za-z0-9]{6,128}$/', $_COOKIE['bolao_uid'])) {
    $uid = $_COOKIE['bolao_uid'];
}

$startUrl = $uid ? ('/user/' . $uid) : '/';

$manifest = [
    'name' => 'Bolão Copa do Mundo 2026',
    'short_name' => 'Bolão Copa',
    'description' => 'Faça seus palpites nos jogos da Copa do Mundo 2026 e acompanhe o ranking ao vivo.',
    'id' => '/',
    'start_url' => $startUrl,
    'scope' => '/',
    'display' => 'standalone',
    'display_override' => ['standalone', 'minimal-ui'],
    'orientation' => 'portrait-primary',
    'background_color' => '#006831',
    'theme_color' => '#009739',
    'lang' => 'pt-BR',
    'dir' => 'ltr',
    'categories' => ['sports', 'games', 'entertainment'],
    'icons' => [
        ['src' => '/assets/img/icon-192.png?v=2', 'sizes' => '192x192', 'type' => 'image/png', 'purpose' => 'any'],
        ['src' => '/assets/img/icon-512.png?v=2', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'any'],
        ['src' => '/assets/img/icon-512.png?v=2', 'sizes' => '512x512', 'type' => 'image/png', 'purpose' => 'maskable'],
    ],
    'shortcuts' => [
        [
            'name' => 'Meus palpites',
            'short_name' => 'Palpites',
            'url' => $startUrl,
            'icons' => [['src' => '/assets/img/icon-192.png?v=2', 'sizes' => '192x192']],
        ],
    ],
];

echo json_encode($manifest, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

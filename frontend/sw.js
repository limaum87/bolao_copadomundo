// Service Worker — Bolão Copa 2026
// Estratégia (PWA Nível 1: instalável + recarga rápida):
//   - Navegações (HTML): network-first com fallback ao cache/offline
//   - Assets estáticos same-origin: stale-while-revalidate
//   - API do backend / dados ao vivo: NUNCA cacheados (sempre rede)
//   - POST (palpites, etc): sempre rede
//
// Bump de versão: troque CACHE abaixo quando atualizar o shell.

const CACHE = 'bolao-shell-v1';

const CORE_ASSETS = [
    '/',
    '/index.php',
    '/offline.html',
    '/manifest.webmanifest',
    '/assets/css/styles.css',
    '/assets/js/flags.js',
    '/assets/js/toast.js',
    '/assets/img/icon-192.png',
    '/assets/img/icon-512.png',
];

// Extensões consideradas estáticas (mesmo-origin).
const STATIC_RE = /\.(?:css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|webmanifest)(\?.*)?$/i;

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE)
            .then((cache) => cache.addAll(CORE_ASSETS))
            // Não falhar a instalação se algum arquivo opcional 404
            .catch((err) => console.warn('[SW] precache parcial:', err))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const req = event.request;

    // Só interceptamos GET. POST/PUT (palpites, login) → rede.
    if (req.method !== 'GET') return;

    const url = new URL(req.url);

    // Cross-origin (ex.: Google Fonts): deixa o navegador cuidar.
    if (url.origin !== self.location.origin) return;

    // Navegação (documentos HTML): network-first.
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req)
                .then((res) => {
                    const copy = res.clone();
                    caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
                    return res;
                })
                .catch(() =>
                    caches.match(req)
                        .then((cached) => cached || caches.match('/index.php') || caches.match('/offline.html'))
                )
        );
        return;
    }

    // Assets estáticos same-origin: stale-while-revalidate.
    if (STATIC_RE.test(url.pathname)) {
        event.respondWith(
            caches.match(req).then((cached) => {
                const network = fetch(req)
                    .then((res) => {
                        if (res && res.status === 200 && res.type === 'basic') {
                            const copy = res.clone();
                            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
                        }
                        return res;
                    })
                    .catch(() => cached);
                return cached || network;
            })
        );
        return;
    }

    // Qualquer outra coisa (ex.: chamadas à API do bolão /live, /scores)
    // não é interceptada — vai direto para a rede. Dados ao vivo nunca
    // são servidos de cache.
});

// Permite que a página force a ativação imediata após update.
self.addEventListener('message', (event) => {
    if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

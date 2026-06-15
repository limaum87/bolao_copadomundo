// Registro do Service Worker + prompt de instalação (PWA)
(function () {
    'use strict';

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker
                .register('/sw.js', { scope: '/' })
                .then(function (reg) {
                    // Checa por atualizações do SW a cada acesso
                    reg.update();
                })
                .catch(function (err) {
                    console.warn('[PWA] registro do SW falhou:', err);
                });
        });

        // Recarrega quando um novo SW assume o controle (após update)
        var refreshing = false;
        navigator.serviceWorker.addEventListener('controllerchange', function () {
            if (refreshing) return;
            refreshing = true;
            window.location.reload();
        });
    }

    // Captura o evento de instalação para podermos oferecer um botão "Instalar app".
    var deferredPrompt = null;
    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        window.dispatchEvent(new CustomEvent('pwa:installable'));
    });

    // API pública: tentar disparar o prompt de instalação (usar em um botão).
    window.bolaoInstall = function () {
        if (!deferredPrompt) return false;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
            deferredPrompt = null;
        });
        return true;
    };

    window.addEventListener('appinstalled', function () {
        deferredPrompt = null;
        console.log('[PWA] app instalado');
    });
})();

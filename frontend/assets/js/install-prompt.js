// Banner "Instalar app" no perfil do participante.
//
// Comportamento por plataforma:
//   - App já instalado (standalone): banner oculto.
//   - iPhone/iPad (sem API de instalação): mostra botão "Como instalar"
//     que expande um tutorial passo-a-passo do Safari.
//   - Android/Desktop (Chromium): mostra botão "Instalar" assim que o
//     prompt nativo (beforeinstallprompt) fica disponível, e dispara-o.
//
// O banner pode ser dispensado (grava em localStorage).
(function () {
    'use strict';

    var banner = document.getElementById('installBanner');
    if (!banner) return;

    var installBtn = document.getElementById('installBtn');
    var iosBtn = document.getElementById('iosInstallBtn');
    var iosTutorial = document.getElementById('iosTutorial');
    var dismissBtn = document.getElementById('installDismiss');

    function isStandalone() {
        return window.matchMedia('(display-mode: standalone)').matches
            || window.matchMedia('(display-mode: window-controls-overlay)').matches
            || window.navigator.standalone === true;
    }

    // iPhone/iPad/iPod. No iPadOS 13+ o UA parece macOS, mas tem touch.
    function isIOS() {
        var ua = navigator.userAgent || '';
        if (/iphone|ipad|ipod/i.test(ua)) return true;
        if (/macintosh|mac os x/i.test(ua) && navigator.maxTouchPoints && navigator.maxTouchPoints > 1) return true;
        return false;
    }

    function isDismissed() {
        try { return localStorage.getItem('bolao_install_dismissed') === '1'; } catch (e) { return false; }
    }
    function dismiss() {
        try { localStorage.setItem('bolao_install_dismissed', '1'); } catch (e) {}
        banner.style.display = 'none';
    }

    function toast(msg, type) {
        if (typeof window.showToast === 'function') window.showToast(msg, type);
        else if (typeof window.Toastify === 'function') window.Toastify({ text: msg, duration: 3500 }).showToast();
    }

    // Já está rodando como app instalado → não mostra nada.
    if (isStandalone() || isDismissed()) {
        banner.style.display = 'none';
        return;
    }

    if (isIOS()) {
        // iOS não possui prompt nativo de instalação → tutorial manual.
        banner.style.display = '';
        installBtn.style.display = 'none';
        iosBtn.style.display = '';
        iosBtn.addEventListener('click', function () {
            var isOpen = iosTutorial.style.display !== 'none';
            iosTutorial.style.display = isOpen ? 'none' : '';
            iosBtn.textContent = isOpen ? 'Como instalar' : 'Fechar instruções';
        });
    } else {
        // Android/Desktop: habilita o botão quando o prompt nativo existir.
        function enableInstall() {
            banner.style.display = '';
            installBtn.style.display = '';
        }
        if (window.__bolaoInstallable) enableInstall();          // já capturado antes deste script
        window.addEventListener('pwa:installable', enableInstall); // capturado depois

        installBtn.addEventListener('click', function () {
            if (typeof window.bolaoInstall !== 'function') {
                toast('Atualize a página e tente novamente.', 'warning');
                return;
            }
            var ok = window.bolaoInstall();
            if (!ok) {
                toast('Continue usando o app por alguns segundos e tente de novo 😉', 'info');
            }
        });
    }

    // Após instalar com sucesso, esconde o banner.
    window.addEventListener('appinstalled', function () {
        banner.style.display = 'none';
    });

    if (dismissBtn) dismissBtn.addEventListener('click', dismiss);
})();

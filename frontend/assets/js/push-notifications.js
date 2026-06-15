// Notificações Push (Web Push / VAPID) — Bolão Copa 2026
//
// Depende de variáveis globais definidas em user.php:
//   - apiBase  (URL do backend)
//   - uid      (identificador secreto do participante)
//
// Comportamento:
//   - Só oferece "Ativar notificações" se: navegador suporta push + service
//     worker + o backend tem VAPID configurado.
//   - Pede permissão só quando o usuário clica (não enche o saco sozinho).
//   - Se já concedido, garante a inscrição (reinscreve se necessário).
//   - Em "pushsubscriptionchange" (navegador renovou/invalidou), reinscreve.
(function () {
    'use strict';

    function cfg() {
        // apiBase/uid são const globais declaradas em user.php (mesmo escopo
        // lexical global). Lemos defensivamente.
        return {
            apiBase: (typeof apiBase !== 'undefined') ? apiBase : window.apiBase,
            uid: (typeof uid !== 'undefined') ? uid : window.uid,
        };
    }

    function supportsPush() {
        return ('serviceWorker' in navigator) &&
               ('PushManager' in window) &&
               ('Notification' in window) &&
               (window.isSecureContext === true);
    }

    // Converte a chave pública VAPID (base64url) para Uint8Array (exigido pelo
    // PushManager.subscribe).
    function urlBase64ToUint8Array(base64Url) {
        const padding = '='.repeat((4 - (base64Url.length % 4)) % 4);
        const base64 = (base64Url + padding).replace(/-/g, '+').replace(/_/g, '/');
        const raw = atob(base64);
        const arr = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
        return arr;
    }

    async function getVapid() {
        const { apiBase } = cfg();
        try {
            const res = await fetch(apiBase + '/push/vapid-public');
            if (!res.ok) return { enabled: false, publicKey: null };
            const data = await res.json();
            return { enabled: !!data.enabled, publicKey: data.publicKey || null };
        } catch (e) {
            return { enabled: false, publicKey: null };
        }
    }

    async function sendSubscriptionToServer(subscription) {
        const { apiBase, uid } = cfg();
        if (!uid) return false;
        try {
            const res = await fetch(apiBase + '/push/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ participant_uid: uid, subscription }),
            });
            return res.ok;
        } catch (e) {
            console.warn('[push] erro ao enviar inscrição:', e);
            return false;
        }
    }

    async function removeSubscriptionFromServer(endpoint) {
        const { apiBase } = cfg();
        try {
            await fetch(apiBase + '/push/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint }),
            });
        } catch (e) {
            /* silencioso */
        }
    }

    // Cria (ou retorna) a inscrição push e registra no backend.
    async function subscribeUser() {
        const { publicKey } = await getVapid();
        if (!publicKey) {
            showToast && showToast('Notificações não configuradas no servidor.', 'warning');
            return false;
        }
        const reg = await navigator.serviceWorker.ready;
        let subscription = await reg.pushManager.getSubscription();
        if (!subscription) {
            subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
        }
        const ok = await sendSubscriptionToServer(subscription.toJSON());
        return ok;
    }

    // ---- UI: banner "Ativar notificações" ---------------------------------
    function mountBanner() {
        const root = document.querySelector('.main-content .container');
        if (!root) return;
        if (document.getElementById('pushBanner')) return;

        const banner = document.createElement('div');
        banner.id = 'pushBanner';
        banner.className = 'push-banner';
        banner.innerHTML = `
            <div class="push-banner-inner">
                <div class="push-banner-text">
                    <strong>🔔 Quer ser avisado dos seus jogos?</strong>
                    <span>Receba um lembrete antes de cada jogo e o aviso de resultado.</span>
                </div>
                <div class="push-banner-actions">
                    <button type="button" class="btn btn-primary btn-sm" id="pushEnableBtn">
                        🔔 Ativar
                    </button>
                    <button type="button" class="push-banner-close" id="pushDismissBtn"
                        aria-label="Fechar">×</button>
                </div>
            </div>
        `;
        root.insertBefore(banner, root.firstChild);

        document.getElementById('pushEnableBtn').addEventListener('click', onEnableClick);
        document.getElementById('pushDismissBtn').addEventListener('click', () => {
            banner.remove();
            try { sessionStorage.setItem('pushBannerDismissed', '1'); } catch (e) {}
        });
    }

    function showActiveIndicator() {
        const old = document.getElementById('pushActiveIndicator');
        if (old) return;
        const root = document.querySelector('.main-content .container');
        if (!root) return;
        const ind = document.createElement('div');
        ind.id = 'pushActiveIndicator';
        ind.className = 'push-active-indicator';
        ind.innerHTML = '🔔 Notificações ativas';
        root.appendChild(ind); // no rodapé do conteúdo (não cobre o card ao vivo)
    }

    async function onEnableClick() {
        const btn = document.getElementById('pushEnableBtn');
        if (btn) { btn.disabled = true; btn.textContent = 'Aguarde...'; }
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                if (typeof showToast === 'function') {
                    showToast('Permissão negada. Você pode ativar depois nas configurações do navegador.', 'warning');
                }
                return;
            }
            const ok = await subscribeUser();
            if (ok) {
                const banner = document.getElementById('pushBanner');
                if (banner) banner.remove();
                if (typeof showToast === 'function') showToast('✅ Notificações ativadas!', 'success');
                showActiveIndicator();
            } else {
                if (typeof showToast === 'function') showToast('Não consegui ativar as notificações. Tente novamente.', 'error');
            }
        } catch (e) {
            console.error('[push] erro ao ativar:', e);
            if (typeof showToast === 'function') showToast('Erro ao ativar notificações.', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🔔 Ativar'; }
        }
    }

    async function init() {
        if (!supportsPush()) return; // contexto não-seguro (http sem ser localhost) ou sem suporte
        const { enabled } = await getVapid();
        if (!enabled) return; // servidor sem VAPID

        const permission = Notification.permission;

        if (permission === 'granted') {
            // Garante inscrição ativa (ex.: após reinstalação / troca de dispositivo).
            try {
                const reg = await navigator.serviceWorker.ready;
                const sub = await reg.pushManager.getSubscription();
                if (sub) {
                    await sendSubscriptionToServer(sub.toJSON());
                }
            } catch (e) {
                /* não crítico */
            }
            showActiveIndicator();
            return;
        }

        if (permission === 'denied') return; // usuário já bloqueou; não podemos insistir

        // permission === 'default' → oferece o banner (a menos que tenha dispensado)
        let dismissed = false;
        try { dismissed = sessionStorage.getItem('pushBannerDismissed') === '1'; } catch (e) {}
        if (!dismissed) mountBanner();

        // Renovação automática pelo navegador.
        navigator.serviceWorker.ready.then((reg) => {
            return reg.pushManager.getSubscription();
        }).then((sub) => {
            if (sub && Notification.permission === 'granted') sendSubscriptionToServer(sub.toJSON());
        });
    }

    // "pushsubscriptionchange": navegador invalidou/renovou a inscrição.
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'pushsubscriptionchange') {
                subscribeUser();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // API pública (botão opcional, ex.: no menu)
    window.bolaoEnableNotifications = onEnableClick;
})();

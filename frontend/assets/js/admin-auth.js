/**
 * admin-auth.js — Interceptor global de autenticação admin.
 *
 * - Verifica se o token existe ao carregar a página; se não, redireciona para login.
 * - Intercepta TODAS as respostas fetch que retornam 401 e faz logout automático.
 * - Mostra toast amigável ("Sessão expirada") antes de redirecionar.
 *
 * Deve ser incluído DEPOIS do toast.js em todas as páginas admin.
 */

(function () {
    const TOKEN_KEY = 'admin_token';
    const LOGIN_URL = '/admin/login.php';

    // Se não há token, manda direto para login
    const _token = localStorage.getItem(TOKEN_KEY);
    if (!_token) {
        window.location.href = LOGIN_URL;
        return; // impede resto do script de executar
    }

    // Guarda referência original do fetch
    const originalFetch = window.fetch;

    // Substitui window.fetch por versão que intercepta 401
    window.fetch = function (...args) {
        return originalFetch.apply(this, args).then(function (response) {
            if (response.status === 401) {
                localStorage.removeItem(TOKEN_KEY);
                if (typeof showToast === 'function') {
                    showToast('🔒 Sessão expirada. Faça login novamente.', 'warning');
                }
                setTimeout(function () {
                    window.location.href = LOGIN_URL;
                }, 1500);
            }
            return response;
        });
    };

    // Expõe helper para obter o token (usado nas páginas)
    window.getAdminToken = function () {
        return localStorage.getItem(TOKEN_KEY);
    };

    // Expõe helper de logout
    window.adminLogout = function () {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = LOGIN_URL;
    };
})();

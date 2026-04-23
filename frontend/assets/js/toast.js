const toastStyles = {
    success: { background: '#10b981', color: '#fff' },
    error:   { background: '#ef4444', color: '#fff' },
    warning: { background: '#f59e0b', color: '#fff' },
    info:    { background: '#3b82f6', color: '#fff' },
};

function showToast(message, type = 'success') {
    const style = toastStyles[type] || toastStyles.success;
    Toastify({
        text: message,
        duration: 3500,
        gravity: 'bottom',
        position: 'right',
        escapeMarkup: false,
        style: {
            background: style.background,
            color: style.color,
            borderRadius: '8px',
            padding: '12px 20px',
            fontFamily: 'Inter, sans-serif',
            fontSize: '0.95rem',
            boxShadow: '0 4px 14px rgba(0,0,0,0.2)',
        },
        offset: { y: 20, x: 20 },
    }).showToast();
}

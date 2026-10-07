import { useState, useEffect } from 'react';

export const toast = (message, type = 'info') => {
    window.dispatchEvent(new CustomEvent('add-toast', { detail: { message, type } }));
};

export default function ToastContainer() {
    const [toasts, setToasts] = useState([]);

    useEffect(() => {
        const handleAdd = (e) => {
            const id = Date.now() + Math.random();
            setToasts(prev => [...prev, { id, ...e.detail }]);
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, 3500);
        };
        window.addEventListener('add-toast', handleAdd);
        return () => window.removeEventListener('add-toast', handleAdd);
    }, []);

    return (
        <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none">
            {toasts.map(t => (
                <div 
                    key={t.id} 
                    className="animate-slide-up flex items-center px-4 py-3 rounded-xl shadow-[var(--shadow-lg)] border bg-[var(--bg-elevated)] text-[var(--text-primary)] font-medium text-sm min-w-[300px] pointer-events-auto"
                    style={{
                        borderColor: t.type === 'error' ? 'var(--risk-high)' : t.type === 'success' ? 'var(--risk-low)' : 'var(--accent)'
                    }}
                >
                    <span className="mr-3">
                        {t.type === 'error' ? '⚠️' : t.type === 'success' ? '✅' : 'ℹ️'}
                    </span>
                    {t.message}
                </div>
            ))}
        </div>
    );
}

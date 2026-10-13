export const toast = (message, type = 'info') => {
    window.dispatchEvent(new CustomEvent('add-toast', { detail: { message, type } }));
};

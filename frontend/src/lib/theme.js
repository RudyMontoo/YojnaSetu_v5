// Theme management
export function getTheme() {
    return localStorage.getItem('yojna_theme') || 'dark'
}

export function setTheme(theme) {
    localStorage.setItem('yojna_theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
    // Lets non-CSS consumers (e.g. the WebGL chakra background, whose colors
    // are hardcoded THREE.Color values, not CSS custom properties) react to
    // a live toggle instead of only picking up the theme on next page load.
    window.dispatchEvent(new CustomEvent('yojna-theme-change', { detail: theme }))
}

export function initTheme() {
    const theme = getTheme()
    document.documentElement.setAttribute('data-theme', theme)
}

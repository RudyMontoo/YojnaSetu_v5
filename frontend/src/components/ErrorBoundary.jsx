import { Component } from 'react'

/**
 * App-wide safety net. Before this, ANY render error or a failed lazy-chunk load
 * (classic after a PWA redeploy: the cached app points at an old chunk hash that
 * no longer exists) produced a silent BLACK PAGE — React unmounts the whole tree
 * and there's nothing behind it.
 *
 * Now: a chunk/import error auto-reloads once (a fresh load pulls the new index +
 * chunks and fixes itself). Any other error shows a friendly "reload" card
 * instead of a blank screen.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    const msg = String(error?.message || error || '')
    const isChunkError =
      error?.name === 'ChunkLoadError' ||
      /Loading chunk|dynamically imported module|Failed to fetch dynamically|Importing a module script failed/i.test(msg)

    // Stale-deploy recovery: reload ONCE (guard against a reload loop) so the
    // browser fetches the current index.html + fresh chunk hashes.
    if (isChunkError && !sessionStorage.getItem('chunk-reloaded')) {
      sessionStorage.setItem('chunk-reloaded', '1')
      window.location.reload()
    }
  }

  render() {
    if (this.state.failed) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24,
          textAlign: 'center', color: '#e8e8ea', background: '#0b0b12',
        }}>
          <div style={{ fontSize: 40 }}>🙏</div>
          <h2 style={{ margin: 0, fontSize: 20 }}>Kuch technical dikkat aa gayi</h2>
          <p style={{ margin: 0, maxWidth: 340, opacity: 0.7, fontSize: 14, lineHeight: 1.5 }}>
            Something went wrong loading this page. Please reload — this usually fixes it.
          </p>
          <button
            onClick={() => { sessionStorage.removeItem('chunk-reloaded'); window.location.reload() }}
            style={{
              marginTop: 8, padding: '10px 22px', borderRadius: 10, border: 'none',
              background: '#ff8c1a', color: '#12121a', fontWeight: 700, fontSize: 15, cursor: 'pointer',
            }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

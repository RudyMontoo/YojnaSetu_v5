import { Info } from 'lucide-react'
import { useLang } from '../lib/i18n'
import './Disclaimer.css'

/**
 * Trust/liability notice: Yojna Sarthi is NOT a government site, and AI
 * eligibility answers must be verified on the official portal.
 *   variant="site" — brand-level (sign-in, footers): "not a government website".
 *   variant="ai"   — near AI output (chat, scheme eligibility): "Sathi can make mistakes".
 * Localised via the existing i18n dictionary (disclaimer.site / disclaimer.ai).
 */
export default function Disclaimer({ variant = 'site', className = '', style }) {
  const { t } = useLang()
  const key = variant === 'ai' ? 'disclaimer.ai' : 'disclaimer.site'
  return (
    <p className={`ys-disclaimer ${className}`} role="note" style={style}>
      <Info size={13} aria-hidden="true" />
      <span>{t(key)}</span>
    </p>
  )
}

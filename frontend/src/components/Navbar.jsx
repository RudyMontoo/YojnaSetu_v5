import { NavLink } from 'react-router-dom'
import { Home, MessageCircle, FileText, Radio, User, Camera } from 'lucide-react'
import './Navbar.css'

const NAV_ITEMS = [
    { to: '/home', label: 'Home', Icon: Home },
    { to: '/chat', label: 'Sathi', Icon: MessageCircle },
    { to: '/schemes', label: 'Schemes', Icon: FileText },
    { to: '/status', label: 'Status', Icon: Radio },
    { to: '/scanner', label: 'Lens', Icon: Camera },
    { to: '/profile', label: 'Profile', Icon: User },
]

/* Animated SVG Logo removed - User requested original logo.png */

/* Top navigation for desktop */
export function Navbar() {
    return (
        <nav className="navbar">
            <NavLink to="/home" className="navbar-logo">
                <div className="logo-img-circle">
                    <img src="/logo.png" alt="Yojna Setu" className="logo-img" />
                </div>
            </NavLink>
            <div className="navbar-links">
                {NAV_ITEMS.map(({ to, label }) => (
                    <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        {label}
                    </NavLink>
                ))}
            </div>
        </nav>
    )
}

/* Bottom tab bar for mobile */
export function BottomNav() {
    return (
        <nav className="bottom-nav">
            {NAV_ITEMS.map((item) => {
                const NavIcon = item.Icon
                return (
                    <NavLink key={item.to} to={item.to} className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}>
                        <NavIcon size={20} />
                        <span>{item.label}</span>
                    </NavLink>
                )
            })}
        </nav>
    )
}

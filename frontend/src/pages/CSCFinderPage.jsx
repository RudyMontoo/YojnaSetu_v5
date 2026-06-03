import { MapPin, Phone, Clock, Navigation, Star } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './CSCFinderPage.css'

const CSC_CENTRES = [
    {
        name: 'Jan Seva Kendra – Peth Naka',
        address: 'Near Gram Panchayat, Peth Naka, Pune – 412101',
        distance: '0.8 km',
        phone: '+91-98765-43210',
        hours: 'Mon–Sat: 9AM – 6PM',
        rating: 4.5,
        services: ['PM-Kisan', 'Aadhaar', 'PAN Card', 'Passport'],
    },
    {
        name: 'Common Service Centre – Chinchwad',
        address: 'Shop No. 4, Mahadeo Nagar, Chinchwad, Pune – 411033',
        distance: '2.3 km',
        phone: '+91-87654-32109',
        hours: 'Mon–Sat: 10AM – 7PM',
        rating: 4.2,
        services: ['Ayushman', 'PMAY', 'Birth Cert.', 'E-Shram'],
    },
    {
        name: 'Gram Panchayat Seva Kendra',
        address: 'Main Road, Talegaon, Pune – 410507',
        distance: '4.1 km',
        phone: '+91-70123-45678',
        hours: 'Mon–Fri: 9AM – 5PM',
        rating: 4.0,
        services: ['PM-Kisan', 'Ration Card', 'Land Records'],
    },
]

function StarRating({ rating }) {
    return (
        <div className="csc-stars">
            {[1, 2, 3, 4, 5].map(i => (
                <Star key={i} size={12} fill={i <= Math.round(rating) ? '#F59E0B' : 'none'} stroke="#F59E0B" />
            ))}
            <span className="csc-rating-text">{rating}</span>
        </div>
    )
}

export default function CSCFinderPage() {
    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="csc-header">
                    <h1 className="csc-title">CSC / Jan Seva Kendra Finder 📍</h1>
                    <p className="text-muted csc-sub">Apne najdeek help centre dhundein</p>
                </div>

                {/* Map placeholder */}
                <div className="glass-card csc-map-card">
                    <div className="csc-map-placeholder">
                        <MapPin size={36} className="text-saffron" />
                        <p className="text-muted csc-map-text">Map loading… (GPS access required)</p>
                        <button className="btn btn-primary btn-sm">Enable Location Access</button>
                    </div>
                </div>

                {/* Nearest CSC list */}
                <h2 className="csc-list-title">Najdeek Kendra ({CSC_CENTRES.length})</h2>
                <div className="csc-list">
                    {CSC_CENTRES.map((csc, i) => (
                        <div key={i} className="glass-card csc-card">
                            <div className="csc-card-top">
                                <div className="csc-icon-wrap">
                                    <MapPin size={20} className="text-saffron" />
                                </div>
                                <div className="csc-info">
                                    <p className="csc-name">{csc.name}</p>
                                    <p className="text-muted csc-address">{csc.address}</p>
                                    <StarRating rating={csc.rating} />
                                </div>
                                <div className="csc-distance">
                                    <span className="badge badge-green">{csc.distance}</span>
                                </div>
                            </div>

                            <div className="csc-details">
                                <div className="csc-detail-row">
                                    <Phone size={13} className="text-muted" />
                                    <a href={`tel:${csc.phone}`} className="text-muted csc-detail-text">{csc.phone}</a>
                                </div>
                                <div className="csc-detail-row">
                                    <Clock size={13} className="text-muted" />
                                    <span className="text-muted csc-detail-text">{csc.hours}</span>
                                </div>
                            </div>

                            <div className="csc-services">
                                {csc.services.map(s => <span key={s} className="badge badge-muted">{s}</span>)}
                            </div>

                            <div className="csc-actions">
                                <a href={`https://maps.google.com?q=${encodeURIComponent(csc.address)}`} target="_blank" rel="noreferrer" className="btn btn-primary btn-sm">
                                    <Navigation size={14} /> Directions
                                </a>
                                <a href={`tel:${csc.phone}`} className="btn btn-ghost btn-sm">
                                    <Phone size={14} /> Call
                                </a>
                            </div>
                        </div>
                    ))}
                </div>
            </main>
            <BottomNav />
        </div>
    )
}

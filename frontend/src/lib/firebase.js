import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

// Public Firebase config — these are project IDENTIFIERS, not secrets (Firebase's
// own docs say they're safe in client code). Real security comes from the
// Authorized-domains list + the backend service-account key. Phone Auth lets
// Google send the SMS OTP, so we need no DLT, no SIM, and no WhatsApp Business
// account. The backend verifies the resulting token before issuing our session.
const firebaseConfig = {
  apiKey: 'AIzaSyBWHrDUcz0QFLngyJf46IEhXdudYRmTpMU',
  authDomain: 'yojna-sarthi.firebaseapp.com',
  projectId: 'yojna-sarthi',
  storageBucket: 'yojna-sarthi.firebasestorage.app',
  messagingSenderId: '597628880042',
  appId: '1:597628880042:web:49de83e22c1faf0d1dbcd3',
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
auth.useDeviceLanguage() // reCAPTCHA + SMS text follow the user's browser language

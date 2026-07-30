package com.yojnasetu.gateway.service;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseToken;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

/**
 * Verifies the ID token that Firebase Phone Authentication hands the browser
 * after the user enters their SMS OTP. Google sends the OTP from its own
 * infrastructure (no DLT, no SIM, no WhatsApp Business account); our only job is
 * to prove the token is genuine and read the verified phone number out of it.
 *
 * Optional, like EmailService: if FIREBASE_CREDENTIALS_JSON isn't set, phone
 * login is simply "not configured" and the app still boots (email OTP unaffected).
 * The credential is a Firebase service-account JSON (Project Settings → Service
 * accounts → Generate new private key), passed in as a secret env var.
 */
@Service
public class FirebaseTokenService {

    @Value("${firebase.credentials-json:}")
    private String credentialsJson;

    private FirebaseAuth auth;   // null until/unless initialized

    @PostConstruct
    void init() {
        if (credentialsJson == null || credentialsJson.isBlank()) {
            System.out.println("INFO: Firebase phone auth not configured (FIREBASE_CREDENTIALS_JSON unset) — phone OTP disabled, email OTP unaffected.");
            return;
        }
        try {
            // Accept either raw JSON or base64(JSON) — the service-account file is
            // multi-line, which is awkward as a cloud secret, so base64 is easier.
            String json = credentialsJson.trim();
            if (!json.startsWith("{")) {
                json = new String(java.util.Base64.getDecoder().decode(json), StandardCharsets.UTF_8);
            }
            FirebaseOptions options = FirebaseOptions.builder()
                    .setCredentials(GoogleCredentials.fromStream(
                            new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8))))
                    .build();
            FirebaseApp app = FirebaseApp.getApps().isEmpty()
                    ? FirebaseApp.initializeApp(options)
                    : FirebaseApp.getInstance();
            this.auth = FirebaseAuth.getInstance(app);
            System.out.println("INFO: Firebase phone auth initialized.");
        } catch (Exception e) {
            System.err.println("WARNING: Firebase init failed (" + e.getClass().getSimpleName() + ": " + e.getMessage()
                    + ") — phone OTP will be unavailable.");
        }
    }

    public boolean isEnabled() {
        return auth != null;
    }

    /**
     * Verifies a Firebase ID token and returns the E.164 phone number it proves
     * (e.g. "+919876543210"), or null if the token is invalid / carries no phone.
     */
    public String verifiedPhone(String idToken) {
        if (auth == null || idToken == null || idToken.isBlank()) return null;
        try {
            FirebaseToken decoded = auth.verifyIdToken(idToken);
            Object phone = decoded.getClaims().get("phone_number");
            return (phone instanceof String s && !s.isBlank()) ? s : null;
        } catch (Exception e) {
            return null;  // invalid/expired/forged token
        }
    }
}

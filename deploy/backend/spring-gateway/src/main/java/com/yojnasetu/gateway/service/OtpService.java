package com.yojnasetu.gateway.service;

import com.twilio.rest.api.v2010.account.Message;
import com.twilio.type.PhoneNumber;
import com.yojnasetu.gateway.model.OtpSession;
import com.yojnasetu.gateway.repository.OtpSessionRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Optional;

/**
 * OTP generation, delivery, and verification per docs/PRANJAL_HANDOFF.md's
 * spec. TTL (10 min) is enforced at the MongoDB level via a TTL index on
 * otp_sessions.expiresAt (see MongoConfig) — this service just sets that
 * field correctly, it doesn't need to remember to clean up expired sessions.
 *
 * Twilio credentials are optional here: if TWILIO_ACCOUNT_SID/AUTH_TOKEN
 * aren't set, the OTP is logged instead of sent — loud, not silent, and
 * lets the whole auth flow be exercised end-to-end without a funded Twilio
 * account. Never do this in production; the missing-credentials branch says
 * so explicitly in its log line.
 */
@Service
public class OtpService {

    private static final int OTP_LENGTH = 6;
    private static final int TTL_MINUTES = 10;
    private static final int MAX_ATTEMPTS = 5;

    private final OtpSessionRepository otpSessionRepository;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();

    @Value("${twilio.account-sid:}")
    private String twilioAccountSid;

    @Value("${twilio.auth-token:}")
    private String twilioAuthToken;

    @Value("${twilio.from-number:}")
    private String twilioFromNumber;

    private boolean twilioInitialized = false;

    public OtpService(OtpSessionRepository otpSessionRepository) {
        this.otpSessionRepository = otpSessionRepository;
    }

    private synchronized void ensureTwilioInit() {
        if (!twilioInitialized && !twilioAccountSid.isBlank() && !twilioAuthToken.isBlank()) {
            com.twilio.Twilio.init(twilioAccountSid, twilioAuthToken);
            twilioInitialized = true;
        }
    }

    public String generateAndSend(String phone) {
        String otp = String.format("%0" + OTP_LENGTH + "d", random.nextInt((int) Math.pow(10, OTP_LENGTH)));

        OtpSession session = otpSessionRepository.findByPhone(phone).orElse(new OtpSession());
        session.setPhone(phone);
        session.setOtpHash(passwordEncoder.encode(otp));
        session.setAttemptCount(0);
        session.setExpiresAt(LocalDateTime.now().plusMinutes(TTL_MINUTES));
        otpSessionRepository.save(session);

        if (twilioAccountSid.isBlank() || twilioAuthToken.isBlank() || twilioFromNumber.isBlank()) {
            System.err.println("WARNING: Twilio not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER) — "
                    + "OTP for " + phone + " is: " + otp + " (logged instead of sent, dev-only fallback)");
        } else {
            ensureTwilioInit();
            Message.creator(
                    new PhoneNumber(phone),
                    new PhoneNumber(twilioFromNumber),
                    "Aapka Yojna Setu OTP: " + otp + ". 10 minute mein expire ho jayega. Kisi ke saath share na karein."
            ).create();
        }

        return otp; // returned only so callers/tests can assert on it in dev; production callers should ignore the return value
    }

    public enum VerifyResult { SUCCESS, EXPIRED_OR_NOT_FOUND, WRONG_OTP, LOCKED }

    public VerifyResult verify(String phone, String otp) {
        Optional<OtpSession> maybeSession = otpSessionRepository.findByPhone(phone);
        if (maybeSession.isEmpty()) return VerifyResult.EXPIRED_OR_NOT_FOUND;

        OtpSession session = maybeSession.get();
        if (session.getExpiresAt().isBefore(LocalDateTime.now())) {
            otpSessionRepository.deleteByPhone(phone);
            return VerifyResult.EXPIRED_OR_NOT_FOUND;
        }
        if (session.getAttemptCount() >= MAX_ATTEMPTS) {
            return VerifyResult.LOCKED;
        }

        if (passwordEncoder.matches(otp, session.getOtpHash())) {
            otpSessionRepository.deleteByPhone(phone);
            return VerifyResult.SUCCESS;
        } else {
            session.setAttemptCount(session.getAttemptCount() + 1);
            otpSessionRepository.save(session);
            return session.getAttemptCount() >= MAX_ATTEMPTS ? VerifyResult.LOCKED : VerifyResult.WRONG_OTP;
        }
    }
}

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
 * OTP generation, delivery, and verification per the auth
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

    /** Anti-bombing throttle, per identifier (phone/email). `/auth/otp/send` is a
     *  public endpoint, so without this a victim's inbox/phone can be flooded and,
     *  for SMS, run up toll-fraud charges. 30s minimum between sends, 5 per rolling hour. */
    private static final int RESEND_COOLDOWN_SECONDS = 30;
    private static final int MAX_SENDS_PER_WINDOW = 5;
    private static final int SEND_WINDOW_MINUTES = 60;

    /** Thrown when an identifier exceeds the send throttle; AuthController maps it to HTTP 429. */
    public static class OtpRateLimitException extends RuntimeException {
        public OtpRateLimitException(String message) { super(message); }
    }

    private final OtpSessionRepository otpSessionRepository;
    private final EmailService emailService;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();

    /** Which channel to deliver the OTP over — decides SMS/log vs email. */
    public enum Channel { SMS, EMAIL }

    @Value("${twilio.account-sid:}")
    private String twilioAccountSid;

    @Value("${twilio.auth-token:}")
    private String twilioAuthToken;

    @Value("${twilio.from-number:}")
    private String twilioFromNumber;

    /** See EmailService.devEcho — opt-in dev-only credential echo, never set in prod. */
    @Value("${app.dev-credential-echo:false}")
    private boolean devEcho;

    private boolean twilioInitialized = false;

    public OtpService(OtpSessionRepository otpSessionRepository, EmailService emailService) {
        this.otpSessionRepository = otpSessionRepository;
        this.emailService = emailService;
    }

    private synchronized void ensureTwilioInit() {
        if (!twilioInitialized && !twilioAccountSid.isBlank() && !twilioAuthToken.isBlank()) {
            com.twilio.Twilio.init(twilioAccountSid, twilioAuthToken);
            twilioInitialized = true;
        }
    }

    public String generateAndSend(String identifier, Channel channel) {
        OtpSession session = otpSessionRepository.findByIdentifier(identifier).orElse(new OtpSession());
        LocalDateTime now = LocalDateTime.now();

        // Anti-bombing: enforce cooldown + rolling-hour cap BEFORE generating/sending.
        if (session.getLastSentAt() != null
                && session.getLastSentAt().plusSeconds(RESEND_COOLDOWN_SECONDS).isAfter(now)) {
            throw new OtpRateLimitException("Please wait a few seconds before requesting another OTP.");
        }
        if (session.getWindowStartAt() == null
                || session.getWindowStartAt().plusMinutes(SEND_WINDOW_MINUTES).isBefore(now)) {
            session.setWindowStartAt(now);
            session.setSendCount(0);
        }
        int sent = session.getSendCount() == null ? 0 : session.getSendCount();
        if (sent >= MAX_SENDS_PER_WINDOW) {
            throw new OtpRateLimitException("Too many OTP requests for this number/email. Try again in an hour.");
        }

        String otp = String.format("%0" + OTP_LENGTH + "d", random.nextInt((int) Math.pow(10, OTP_LENGTH)));

        session.setIdentifier(identifier);
        session.setOtpHash(passwordEncoder.encode(otp));
        session.setAttemptCount(0);
        session.setLastSentAt(now);
        session.setSendCount(sent + 1);
        session.setExpiresAt(now.plusMinutes(TTL_MINUTES));
        otpSessionRepository.save(session);

        if (channel == Channel.EMAIL) {
            emailService.sendOtp(identifier, otp);
        } else if (twilioAccountSid.isBlank() || twilioAuthToken.isBlank() || twilioFromNumber.isBlank()) {
            // Same rule as EmailService: an SMS OTP is a live credential, so it is
            // never logged unless a developer explicitly opts in. Otherwise an
            // unconfigured Twilio silently turned the log into a list of valid
            // login codes paired with the phone numbers they unlock.
            if (devEcho) {
                System.err.println("DEV: OTP for " + identifier + " is: " + otp);
            } else {
                System.err.println("ERROR: Twilio not configured (TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER) — "
                        + "SMS OTP could not be sent and was NOT logged.");
            }
        } else {
            ensureTwilioInit();
            Message.creator(
                    new PhoneNumber(identifier),
                    new PhoneNumber(twilioFromNumber),
                    "Aapka Yojna Sarthi OTP: " + otp + ". 10 minute mein expire ho jayega. Kisi ke saath share na karein."
            ).create();
        }

        return otp; // returned only so callers/tests can assert on it in dev; production callers should ignore the return value
    }

    public enum VerifyResult { SUCCESS, EXPIRED_OR_NOT_FOUND, WRONG_OTP, LOCKED }

    public VerifyResult verify(String identifier, String otp) {
        Optional<OtpSession> maybeSession = otpSessionRepository.findByIdentifier(identifier);
        if (maybeSession.isEmpty()) return VerifyResult.EXPIRED_OR_NOT_FOUND;

        OtpSession session = maybeSession.get();
        if (session.getExpiresAt().isBefore(LocalDateTime.now())) {
            otpSessionRepository.deleteByIdentifier(identifier);
            return VerifyResult.EXPIRED_OR_NOT_FOUND;
        }
        if (session.getAttemptCount() >= MAX_ATTEMPTS) {
            return VerifyResult.LOCKED;
        }

        if (passwordEncoder.matches(otp, session.getOtpHash())) {
            otpSessionRepository.deleteByIdentifier(identifier);
            return VerifyResult.SUCCESS;
        } else {
            session.setAttemptCount(session.getAttemptCount() + 1);
            otpSessionRepository.save(session);
            return session.getAttemptCount() >= MAX_ATTEMPTS ? VerifyResult.LOCKED : VerifyResult.WRONG_OTP;
        }
    }
}

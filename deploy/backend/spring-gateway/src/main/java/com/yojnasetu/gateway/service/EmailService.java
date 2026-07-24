package com.yojnasetu.gateway.service;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

/**
 * Sends the login OTP by email. Mirrors OtpService's Twilio pattern: if SMTP
 * isn't configured (app.mail.enabled=false or no JavaMailSender bean), the code
 * is LOGGED instead of sent — loud, not silent — so the flow can be exercised
 * end-to-end without a mail account. Never rely on the log path in production.
 *
 * JavaMailSender is injected via ObjectProvider so the app still boots when
 * spring.mail.* is unset (no bean) — we just fall back to logging.
 */
@Service
public class EmailService {

    private final ObjectProvider<JavaMailSender> mailSenderProvider;

    @Value("${app.mail.enabled:false}")
    private boolean enabled;

    @Value("${app.mail.from:}")
    private String from;

    public EmailService(ObjectProvider<JavaMailSender> mailSenderProvider) {
        this.mailSenderProvider = mailSenderProvider;
    }

    public void sendOtp(String email, String otp) {
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        if (!enabled || from == null || from.isBlank() || sender == null) {
            System.err.println("WARNING: Email not configured (app.mail.enabled/from + spring.mail.*) — "
                    + "OTP for " + email + " is: " + otp + " (logged instead of sent, dev-only fallback)");
            return;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(from);
        msg.setTo(email);
        msg.setSubject("Yojna Setu OTP: " + otp);
        msg.setText("Aapka Yojna Setu login OTP: " + otp
                + "\n\n10 minute mein expire ho jayega. Kisi ke saath share na karein.\n\n— Yojna Setu");
        sender.send(msg);
    }
}

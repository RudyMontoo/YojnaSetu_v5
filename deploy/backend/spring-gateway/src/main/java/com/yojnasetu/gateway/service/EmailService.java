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

    /** Display name on the From header. A named sender ("Yojna Sarthi <addr>") lands
     *  in the inbox more reliably than a bare address. */
    @Value("${app.mail.from-name:Yojna Sarthi}")
    private String fromName;

    /** Public site URL, for links in emails (helper login). */
    @Value("${app.frontend-url:}")
    private String frontendUrl;

    public EmailService(ObjectProvider<JavaMailSender> mailSenderProvider) {
        this.mailSenderProvider = mailSenderProvider;
    }

    /** "Yojna Sarthi <no-reply@yojsarthi.in>" — unless MAIL_FROM already carries a display name. */
    private String fromHeader() {
        return (from.contains("<") || fromName == null || fromName.isBlank())
                ? from : fromName + " <" + from + ">";
    }

    public void sendOtp(String email, String otp) {
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        if (!enabled || from == null || from.isBlank() || sender == null) {
            System.err.println("WARNING: Email not configured (app.mail.enabled/from + spring.mail.*) — "
                    + "OTP for " + email + " is: " + otp + " (logged instead of sent, dev-only fallback)");
            return;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(fromHeader());
        msg.setTo(email);
        // OTP stays OUT of the subject: keeps it off lock-screen previews and
        // avoids the "code in subject" spam-filter signal.
        msg.setSubject("Your Yojna Sarthi login code");
        msg.setText("Aapka Yojna Sarthi login OTP: " + otp
                + "\n\n10 minute mein expire ho jayega. Kisi ke saath share na karein.\n\n— Yojna Sarthi");
        sender.send(msg);
    }

    /** Emails an approved helper their login credentials. Same log-fallback as above. */
    public void sendCredentials(String email, String name, String helperId, String tempPassword) {
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        String body = "Namaste " + (name != null ? name : "") + ",\n\n"
                + "Aapki Yojna Sarthi Helper application APPROVE ho gayi hai! 🎉\n\n"
                + "Aapke helper portal login details:\n"
                + "  Helper ID: " + helperId + "\n"
                + "  Temporary password: " + tempPassword + "\n\n"
                + "Pehli baar login karne par aapko apna password reset karna hoga.\n"
                + "Login: " + (frontendUrl != null && !frontendUrl.isBlank() ? frontendUrl : "https://yojsarthi.in") + "/helper\n\n"
                + "Kisi ke saath ye details share na karein.\n\n— Yojna Sarthi";
        if (!enabled || from == null || from.isBlank() || sender == null) {
            System.err.println("WARNING: Email not configured — Helper credentials for " + email
                    + " => id=" + helperId + " password=" + tempPassword + " (logged instead of sent)");
            return;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(fromHeader());
        msg.setTo(email);
        msg.setSubject("Yojna Sarthi Helper — your login credentials");
        msg.setText(body);
        sender.send(msg);
    }
}

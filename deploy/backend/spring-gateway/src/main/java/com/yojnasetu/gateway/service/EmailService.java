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

    /** Opt-in ONLY: echo OTPs/credentials to stderr when mail is unconfigured, for
     *  local dev. Defaults false and deploy.sh never sets it, so production can
     *  never log a live credential even if mail breaks. */
    @Value("${app.dev-credential-echo:false}")
    private boolean devEcho;

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
            // NEVER print the OTP unless a developer explicitly asked for it. This
            // branch fires whenever mail is unconfigured — and MAIL_ENABLED defaults
            // to false, so it was the *production* path: every login code landed in
            // Azure Log Analytics next to the address it authenticates, which is
            // account takeover for anyone holding log-read access.
            if (devEcho) {
                System.err.println("DEV: OTP for " + email + " is: " + otp);
            } else {
                System.err.println("ERROR: Email not configured (app.mail.enabled/from + spring.mail.*) — "
                        + "OTP could not be sent and was NOT logged. Login is broken until mail is configured.");
            }
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

    /**
     * Sends an operational alert to the admin (AlertNotifier calls this). Returns
     * true if actually emailed, false if it fell back to logging — the caller uses
     * that to decide whether to mark the alert notified (don't mark on log-only,
     * so it retries once email is really configured).
     */
    public boolean sendAlert(String to, String subject, String body) {
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        if (!enabled || from == null || from.isBlank() || sender == null || to == null || to.isBlank()) {
            System.err.println("WARNING: Email not configured / no alert recipient — ALERT not sent: "
                    + subject + " (logged instead)\n" + body);
            return false;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(fromHeader());
        msg.setTo(to);
        msg.setSubject(subject);
        msg.setText(body);
        sender.send(msg);
        return true;
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
            if (devEcho) {
                System.err.println("DEV: Helper credentials for " + email
                        + " => id=" + helperId + " password=" + tempPassword);
            } else {
                System.err.println("ERROR: Email not configured — Helper credentials for helperId=" + helperId
                        + " could not be sent and were NOT logged. Re-issue them once mail is configured.");
            }
            return;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(fromHeader());
        msg.setTo(email);
        msg.setSubject("Yojna Sarthi Helper — your login credentials");
        msg.setText(body);
        sender.send(msg);
    }

    /**
     * Emails an approved assist-only credit helper (CSC operator, NGO/SHG
     * worker, field agent) their branch-portal login. Deliberately its own
     * method rather than a reuse of {@link #sendCredentials}: that one is
     * hardcoded to say "Helper" and link to {@code /helper}, which is the
     * WRONG login page and the wrong role name for this account — sending it
     * here would point a CSC operator at a portal that isn't theirs. Same
     * log-fallback / dev-echo behaviour as every other credential email in
     * this class.
     */
    public void sendBranchRepCredentials(String email, String name, String repTypeLabel,
                                         String repId, String tempPassword) {
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        String body = "Namaste " + (name != null ? name : "") + ",\n\n"
                + "Aapki Yojna Sarthi " + repTypeLabel + " application APPROVE ho gayi hai! 🎉\n\n"
                + "Aapke branch portal login details:\n"
                + "  Rep ID: " + repId + "\n"
                + "  Temporary password: " + tempPassword + "\n\n"
                + "Pehli baar login karne par aapko apna password reset karna hoga.\n"
                + "Login: " + (frontendUrl != null && !frontendUrl.isBlank() ? frontendUrl : "https://yojsarthi.in") + "/branch-portal\n\n"
                + "Kisi ke saath ye details share na karein.\n\n— Yojna Sarthi";
        if (!enabled || from == null || from.isBlank() || sender == null) {
            if (devEcho) {
                System.err.println("DEV: Branch-rep credentials for " + email
                        + " => id=" + repId + " password=" + tempPassword);
            } else {
                System.err.println("ERROR: Email not configured — branch-rep credentials for repId=" + repId
                        + " could not be sent and were NOT logged. Re-issue them once mail is configured.");
            }
            return;
        }
        SimpleMailMessage msg = new SimpleMailMessage();
        msg.setFrom(fromHeader());
        msg.setTo(email);
        msg.setSubject("Yojna Sarthi — your branch portal login credentials");
        msg.setText(body);
        sender.send(msg);
    }
}

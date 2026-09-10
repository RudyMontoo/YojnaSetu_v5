package com.yojnasetu.gateway.notify;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Every moment in a loan's life that is worth interrupting someone for.
 *
 * Each event carries its own copy for each channel. They are deliberately
 * written as complete sentences rather than assembled from fragments: a
 * citizen who gets "Status: MISSING_DOCS" has been told nothing they can act
 * on, and an SMS is often the only part of this platform they will ever see.
 *
 * Every message states three things — which application, where it now stands,
 * and what the person should do next. If a template cannot answer the third,
 * the event probably should not be sending a message at all.
 */
public enum NotificationEvent {

    APPLICATION_SUBMITTED("application.submitted",
            Audience.CITIZEN,
            "Your {scheme} application ({ref}) has been sent to {partner}. "
                    + "They will contact you if anything else is needed. No action needed right now.",
            "Application sent to {partner}"),

    APPLICATION_UNDER_VERIFICATION("application.under_verification",
            Audience.CITIZEN,
            "{partner} has started checking your {scheme} application ({ref}). "
                    + "Keep your original documents ready in case they ask to see them.",
            "Your application is being checked"),

    APPLICATION_MISSING_DOCS("application.missing_docs",
            Audience.CITIZEN,
            "{partner} needs more documents for your {scheme} application ({ref}): {documents}. "
                    + "Take these to the branch or upload them in the app to continue.",
            "Documents needed for your application"),

    APPLICATION_FORWARDED("application.forwarded",
            Audience.CITIZEN,
            "Your {scheme} application ({ref}) has passed verification and gone to the "
                    + "sanctioning authority. Nothing needed from you now.",
            "Application forwarded for sanction"),

    APPLICATION_SANCTIONED("application.sanctioned",
            Audience.CITIZEN,
            "Good news — your {scheme} loan ({ref}) has been sanctioned. {partner} will tell you "
                    + "when the money reaches your account. Do not pay anyone a fee for this.",
            "Your loan has been sanctioned"),

    APPLICATION_REJECTED("application.rejected",
            Audience.CITIZEN,
            "Your {scheme} application ({ref}) was not approved. Reason: {reason}. "
                    + "You can fix this and apply again — a CSC can help you understand what is needed.",
            "About your application"),

    APPLICATION_DISBURSED("application.disbursed",
            Audience.CITIZEN,
            "Your {scheme} loan ({ref}) has been disbursed. Your first instalment is due after the "
                    + "moratorium ends. Check the app for your repayment schedule.",
            "Your loan has been disbursed"),

    // --- SLA events ---

    VERIFICATION_OVERDUE_REMINDER("verification.overdue_reminder",
            Audience.BRANCH_REP,
            "Application {ref} ({scheme}) has been awaiting verification for {days} days. "
                    + "Please review it or record what is blocking it.",
            "Application awaiting your review"),

    DOCS_UPLOAD_OVERDUE_REMINDER("docs_upload.overdue_reminder",
            Audience.CITIZEN,
            "{partner} is still waiting for documents for your {scheme} application ({ref}): "
                    + "{documents}. Your application cannot move forward until these arrive.",
            "Reminder: documents still needed");

    /** Who the message is for — decides which contact details we look up. */
    public enum Audience { CITIZEN, BRANCH_REP }

    private final String key;
    private final Audience audience;
    private final String body;
    private final String subject;

    NotificationEvent(String key, Audience audience, String body, String subject) {
        this.key = key;
        this.audience = audience;
        this.body = body;
        this.subject = subject;
    }

    @JsonValue
    public String key() {
        return key;
    }

    public Audience audience() {
        return audience;
    }

    public String subject() {
        return subject;
    }

    /**
     * Fills the template. Any placeholder without a value is left as a readable
     * gap rather than the literal "{documents}" — a citizen should never
     * receive our template syntax, and a half-filled sentence is still
     * readable where a raw brace is not.
     */
    public String render(java.util.Map<String, String> params) {
        String out = body;
        var matcher = java.util.regex.Pattern.compile("\\{([a-zA-Z]+)}").matcher(body);
        while (matcher.find()) {
            String name = matcher.group(1);
            String value = params == null ? null : params.get(name);
            out = out.replace("{" + name + "}", value == null || value.isBlank() ? "—" : value);
        }
        return out;
    }
}

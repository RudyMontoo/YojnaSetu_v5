package com.yojnasetu.gateway.notify;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * An in-app notification.
 *
 * This is the channel of record. SMS and email are best-effort — Twilio may be
 * unconfigured, a number may be wrong, a message may silently fail to deliver —
 * so every notification is written here first and delivered outward second. A
 * citizen who never received the SMS can still open the app and find out what
 * happened, and we can tell whether they were ever told.
 */
@Document(collection = "notifications")
@CompoundIndexes({
        @CompoundIndex(name = "recipient_inbox", def = "{'recipientUserId': 1, 'readAt': 1, 'createdAt': -1}")
})
@Data
@NoArgsConstructor
public class Notification {

    @Id
    private String id;

    /** The JWT principal this is addressed to — citizen or branch rep. */
    private String recipientUserId;

    private NotificationEvent event;

    /** Rendered, ready to display. Dynamic text, so translate client-side. */
    private String message;

    private String subject;

    /** The application this concerns, so the UI can deep-link to it. */
    private String applicationId;

    private LocalDateTime createdAt;

    /** Null until the recipient opens it. */
    private LocalDateTime readAt;

    /**
     * Per-channel delivery outcome, recorded rather than assumed. "We sent an
     * SMS" and "an SMS left our process without throwing" are different claims,
     * and only the second is one we can actually make.
     */
    private Delivery sms;
    private Delivery email;

    @Data
    @NoArgsConstructor
    public static class Delivery {
        /** SENT | SKIPPED | FAILED */
        private String outcome;
        /** Why it was skipped or how it failed — never the message contents. */
        private String detail;
        private LocalDateTime at;

        public static Delivery of(String outcome, String detail) {
            Delivery d = new Delivery();
            d.setOutcome(outcome);
            d.setDetail(detail);
            d.setAt(LocalDateTime.now());
            return d;
        }
    }
}

package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * An applicant's report that someone helping them did something they should
 * not have.
 *
 * Assisted access is what makes this scheme reachable, and it is also where
 * the applicant is most exposed: a helper is holding their identity documents,
 * often in a room where the applicant cannot check what is being typed. The
 * known failure modes are specific and worth naming rather than leaving to
 * free text — an unofficial fee, an OTP asked for, wrong details entered, a
 * document used for something else.
 *
 * Filing one does not require proof and does not accuse anyone of a crime. It
 * records that a person felt something was wrong, timestamps it, and puts it
 * in front of a human. A channel that demands evidence before it will listen
 * is a channel that hears nothing.
 */
@Document(collection = "misuse_reports")
@Data
@NoArgsConstructor
public class MisuseReport {

    public enum Category {
        /** Asked for money the scheme does not charge. */
        UNOFFICIAL_FEE("unofficial_fee"),
        /** Asked for an OTP, password, or the applicant's phone. */
        CREDENTIAL_REQUEST("credential_request"),
        /** Entered details the applicant did not give, or knows to be wrong. */
        WRONG_DETAILS("wrong_details"),
        /** Used documents or data for something the applicant did not agree to. */
        DATA_MISUSE("data_misuse"),
        /** Claimed to have done work they did not do, or never followed up. */
        NO_SERVICE("no_service"),
        OTHER("other");

        private final String wireName;

        Category(String wireName) {
            this.wireName = wireName;
        }

        @JsonValue
        public String wireName() {
            return wireName;
        }

        @JsonCreator
        public static Category fromWire(String value) {
            if (value == null || value.isBlank()) {
                return null;
            }
            String normalised = value.trim().toLowerCase().replace('-', '_');
            for (Category category : values()) {
                if (category.wireName.equals(normalised)) {
                    return category;
                }
            }
            throw new IllegalArgumentException("Unknown misuse report category '" + value + "'");
        }
    }

    public enum Status {
        OPEN("open"),
        REVIEWING("reviewing"),
        RESOLVED("resolved");

        private final String wireName;

        Status(String wireName) {
            this.wireName = wireName;
        }

        @JsonValue
        public String wireName() {
            return wireName;
        }

        @JsonCreator
        public static Status fromWire(String value) {
            if (value == null || value.isBlank()) {
                return null;
            }
            String normalised = value.trim().toLowerCase();
            for (Status status : values()) {
                if (status.wireName.equals(normalised)) {
                    return status;
                }
            }
            throw new IllegalArgumentException("Unknown misuse report status '" + value + "'");
        }
    }

    @Id
    private String id;

    @Indexed
    private String citizenId;

    @Indexed
    private String applicationId;

    /**
     * Who is being reported, when the applicant can say. Optional on purpose:
     * "someone at the centre asked me for 500 rupees" is a report worth having
     * even when the applicant never learned the person's name or id.
     */
    @Indexed
    private String reportedHelperId;

    private String reportedHelperName;

    private Category category;

    /** The applicant's own account, in their own words. */
    private String description;

    private Status status = Status.OPEN;

    private LocalDateTime createdAt;
    private LocalDateTime resolvedAt;

    /** What was done about it — written by staff, shown back to the applicant. */
    private String resolutionNote;
}

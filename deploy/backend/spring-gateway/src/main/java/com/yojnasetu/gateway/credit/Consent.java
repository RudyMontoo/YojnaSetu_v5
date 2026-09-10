package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * One record of a citizen agreeing to one specific thing.
 *
 * Append-only in spirit: withdrawing consent sets {@link #revokedAt} rather
 * than deleting the row. "This person agreed on the 3rd and withdrew on the
 * 9th" is a materially different fact from "this person never agreed", and
 * only one of them can be reconstructed from a deletion.
 *
 * {@link #statement} is a copy of the wording shown at the time, not a
 * reference to the current wording. If the text changes later we can still
 * answer what a given person actually agreed to.
 */
@Document(collection = "consents")
@CompoundIndexes({
        @CompoundIndex(name = "citizen_purpose", def = "{'userId': 1, 'purpose': 1, 'grantedAt': -1}")
})
@Data
@NoArgsConstructor
public class Consent {

    @Id
    private String id;

    private String userId;

    private ConsentPurpose purpose;

    /**
     * Set when the consent is specific to one application — sharing with a
     * partner is agreed per loan, not once forever. Null for account-wide
     * purposes such as profile storage.
     */
    private String applicationId;

    /** The exact wording shown to the citizen when they agreed. */
    private String statement;

    private LocalDateTime grantedAt;

    /** Null while the consent still stands. */
    private LocalDateTime revokedAt;

    /**
     * Recorded for the same reason the audit log records it — a consent that
     * cannot be tied to a request is hard to defend later. No other PII here.
     */
    private String ip;

    public boolean isActive() {
        return revokedAt == null;
    }
}

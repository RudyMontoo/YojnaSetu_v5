package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A citizen's authorization for one helper to assist on one application.
 *
 * A branch representative reaches a file because the file was assigned to
 * their branch. An assist-only helper — a CSC operator, an NGO or SHG worker,
 * a field agent — has no such institutional claim, and inventing one would be
 * the wrong answer: it would mean anyone holding a helper account could open
 * any citizen's application. The claim comes from the citizen instead. They
 * say who is helping them, and they can withdraw it.
 *
 * Revoked, never deleted, on the same reasoning as {@link Consent}: a citizen
 * asking "who saw my documents?" is owed the whole answer, including the
 * people who no longer have access. Erasing the row would erase the evidence
 * that is the entire point of recording it — which matters most precisely when
 * something has gone wrong and someone needs to show what happened.
 */
@Document(collection = "assist_authorizations")
@CompoundIndex(name = "application_helper_idx", def = "{'applicationId': 1, 'helperId': 1}")
@Data
@NoArgsConstructor
public class AssistAuthorization {

    @Id
    private String id;

    /** The application being assisted on. */
    @Indexed
    private String applicationId;

    /** The citizen who owns that application and granted this. */
    @Indexed
    private String citizenId;

    /** The helper's {@code BranchRep} document id — the same value their JWT carries. */
    @Indexed
    private String helperId;

    // Denormalized so a citizen's "who helped me" list stays readable even if
    // the helper account is later renamed or deactivated. A list that answers
    // "helper 64f2a..." answers nothing.
    private String helperName;
    private RepType helperType;
    private String helperOrganisation;

    private LocalDateTime grantedAt;

    /** Null while the authorization is live. Set on revocation; the row stays. */
    private LocalDateTime revokedAt;

    /** Free-text, citizen's own words, optional — "helped me at the CSC in Ranchi". */
    private String note;

    public boolean isActive() {
        return revokedAt == null;
    }
}

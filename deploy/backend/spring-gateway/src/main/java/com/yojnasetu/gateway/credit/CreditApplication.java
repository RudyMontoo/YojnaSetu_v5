package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * A citizen's application for a concessional credit product.
 *
 * Separate from the welfare-scheme {@code Application} collection on purpose.
 * That model tracks whether someone followed a link to an external portal; this
 * one is a loan file that a branch rep works, with assignment, document
 * requests, reason codes and a validated state machine. Its unique index also
 * forbids re-applying to the same scheme forever, which is correct for a
 * bookmark and wrong for a loan — a rejected applicant fixing their paperwork
 * and trying again is the normal path, not an error.
 *
 * There is NO unique constraint here. "One live application per scheme" is
 * enforced in the service against {@link CreditApplicationStatus#isActive()},
 * so terminal files stay on record and a fresh attempt is allowed.
 */
@Document(collection = "credit_applications")
@CompoundIndexes({
        @CompoundIndex(name = "citizen_view", def = "{'userId': 1, 'status': 1}"),
        @CompoundIndex(name = "partner_queue", def = "{'assignedPartnerId': 1, 'status': 1, 'submittedAt': -1}")
})
@Data
@NoArgsConstructor
public class CreditApplication {

    @Id
    private String id;

    /** The JWT principal — see ProfileController for the same convention. */
    private String userId;

    private String productId;
    // Denormalized so a queue row renders without a second lookup.
    private String productCode;
    private String productName;

    // --- what the citizen declared, snapshotted at submission ---
    private Long estimatedCost;
    private Long requestedAmount;
    private Long marginMoney;
    private Long declaredAnnualIncome;
    private String declaredCategory;

    /**
     * The repayment terms quoted when they applied. Held as a snapshot rather
     * than recomputed on read: if a rate in credit_products is corrected next
     * week, this citizen's file must still show what they were actually told.
     */
    private QuotedTerms quotedTerms;

    private CreditApplicationStatus status = CreditApplicationStatus.DRAFT;

    private List<StatusEntry> statusHistory = new ArrayList<>();

    // --- partner handling ---
    private String assignedPartnerId;
    private String assignedPartnerName;

    /** Documents a branch rep has asked for, plain-language and citizen-facing. */
    private List<String> missingDocuments = new ArrayList<>();

    private VerificationMode verificationMode;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private LocalDateTime submittedAt;

    @Data
    @NoArgsConstructor
    public static class QuotedTerms {
        private double interestRate;
        private int tenureMonths;
        private int moratoriumMonths;
        private MoratoriumMode moratoriumMode;
        private double emi;
        private double totalInterest;
        private double totalPayment;
    }

    /**
     * One movement through the lifecycle. Append-only — this is what the
     * citizen's status timeline renders and what a decision is answered for, so
     * entries are never rewritten.
     */
    @Data
    @NoArgsConstructor
    public static class StatusEntry {
        private CreditApplicationStatus status;
        private LocalDateTime at;
        /** Who acted — a userId, or null for system transitions. */
        private String byUserId;
        /** Their role at the time, e.g. CITIZEN or BRANCH_REP. */
        private String byRole;
        private ReasonCode reasonCode;
        private String note;
        private List<String> requestedDocuments;
    }
}

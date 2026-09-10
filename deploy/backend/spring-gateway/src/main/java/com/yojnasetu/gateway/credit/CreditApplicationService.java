package com.yojnasetu.gateway.credit;

import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Owns the application lifecycle: creation, the one-live-file-per-scheme rule,
 * and every status change.
 *
 * All transitions funnel through {@link #transition} so the state machine
 * cannot be sidestepped by a new endpoint later. Callers get a typed
 * {@link TransitionException} carrying the HTTP-ish reason, rather than the
 * service reaching for ResponseEntity and dragging web concerns into the
 * decision logic.
 */
@Service
public class CreditApplicationService {

    private final CreditApplicationRepository applications;
    private final CreditProductRepository products;

    /**
     * Optional so the state machine can be unit-tested without a messaging
     * stack — the transition rules are the thing under test there, and a null
     * notifier means "nobody is listening", not "something is broken".
     */
    private final com.yojnasetu.gateway.notify.CreditApplicationNotifier notifier;

    // Explicit, because this class has two constructors. Without it Spring
    // cannot choose between them, gives up, looks for a no-arg constructor and
    // fails the whole context at startup — which no unit test catches, since
    // they all call the test constructor directly.
    @org.springframework.beans.factory.annotation.Autowired
    public CreditApplicationService(CreditApplicationRepository applications,
                                    CreditProductRepository products,
                                    org.springframework.beans.factory.ObjectProvider<
                                            com.yojnasetu.gateway.notify.CreditApplicationNotifier> notifier) {
        this.applications = applications;
        this.products = products;
        this.notifier = notifier.getIfAvailable();
    }

    /** Test constructor — no notifications. */
    public CreditApplicationService(CreditApplicationRepository applications,
                                    CreditProductRepository products) {
        this.applications = applications;
        this.products = products;
        this.notifier = null;
    }

    /** Why a requested change was refused — mapped to a status code at the edge. */
    public enum Failure { NOT_FOUND, CONFLICT, BAD_REQUEST, FORBIDDEN }

    public static class TransitionException extends RuntimeException {
        private final Failure failure;

        public TransitionException(Failure failure, String message) {
            super(message);
            this.failure = failure;
        }

        public Failure failure() {
            return failure;
        }
    }

    // ---------------------------------------------------------------- create

    /**
     * Opens a DRAFT application, snapshotting the product's terms and the
     * citizen's declared figures as they stand today.
     */
    public CreditApplication create(String userId, CreateApplicationRequest request) {
        if (request == null || request.productId() == null || request.productId().isBlank()) {
            throw new TransitionException(Failure.BAD_REQUEST, "productId is required");
        }
        if (request.estimatedCost() == null || request.estimatedCost() <= 0) {
            throw new TransitionException(Failure.BAD_REQUEST, "estimatedCost must be greater than zero");
        }

        CreditProduct product = products.findById(request.productId())
                .filter(CreditProduct::isActive)
                .orElseThrow(() -> new TransitionException(
                        Failure.NOT_FOUND, "Unknown credit product: " + request.productId()));

        // One live file per scheme. Terminal ones don't block — a rejected
        // applicant who fixed their documents is expected to come back.
        applications.findByUserIdAndProductId(userId, product.getId()).stream()
                .filter(a -> a.getStatus().isActive())
                .findAny()
                .ifPresent(existing -> {
                    throw new TransitionException(Failure.CONFLICT,
                            "You already have an application in progress for this scheme (status: "
                                    + existing.getStatus().wireName() + ")");
                });

        VerificationMode mode = request.verificationMode() == null
                ? VerificationMode.MANUAL
                : request.verificationMode();
        if (!mode.isAvailable()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Verification mode '" + mode.wireName() + "' is not available yet — use manual or offline");
        }

        // The scheme's unit-cost band, checked against the project cost — not
        // against the loan, which is separately capped below.
        Long floor = product.getUnitCostFloor();
        Long ceiling = product.getUnitCostCeiling();
        if (floor != null && request.estimatedCost() < floor) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "This scheme starts at projects costing " + Rupees.format(floor)
                            + "; yours is " + Rupees.format(request.estimatedCost()));
        }
        if (ceiling != null && request.estimatedCost() > ceiling) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "This scheme covers projects up to " + Rupees.format(ceiling)
                            + "; yours is " + Rupees.format(request.estimatedCost()));
        }

        long coveredByLoan = Math.round(request.estimatedCost() * (product.getCoveragePct() / 100.0));
        long requestedAmount = Math.min(coveredByLoan, product.getMaxLoanAmount());

        int tenure = request.tenureMonths() == null ? product.getMaxTenureMonths() : request.tenureMonths();
        if (tenure < 1 || tenure > product.getMaxTenureMonths()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "tenureMonths must be between 1 and " + product.getMaxTenureMonths());
        }

        MoratoriumMode moratoriumMode = request.moratoriumMode() == null
                ? MoratoriumMode.CAPITALISE
                : request.moratoriumMode();
        EmiPlan quote = EmiCalculator.calculate(requestedAmount, product.getInterestRate(),
                tenure, product.getMoratoriumMonths(), moratoriumMode);

        CreditApplication application = new CreditApplication();
        application.setUserId(userId);
        application.setProductId(product.getId());
        application.setProductCode(product.getCode());
        application.setProductName(product.getName());
        application.setEstimatedCost(request.estimatedCost());
        application.setRequestedAmount(requestedAmount);
        application.setMarginMoney(request.estimatedCost() - requestedAmount);
        application.setDeclaredAnnualIncome(request.annualIncome());
        application.setDeclaredCategory(request.category());
        application.setVerificationMode(mode);
        application.setQuotedTerms(snapshot(product, tenure, moratoriumMode, quote));
        application.setStatus(CreditApplicationStatus.DRAFT);
        application.setCreatedAt(LocalDateTime.now());
        application.setUpdatedAt(LocalDateTime.now());
        application.getStatusHistory().add(
                entry(CreditApplicationStatus.DRAFT, userId, "CITIZEN", null, null, null));

        return applications.save(application);
    }

    private static CreditApplication.QuotedTerms snapshot(CreditProduct product, int tenure,
                                                          MoratoriumMode mode, EmiPlan quote) {
        CreditApplication.QuotedTerms terms = new CreditApplication.QuotedTerms();
        terms.setInterestRate(product.getInterestRate());
        terms.setTenureMonths(tenure);
        terms.setMoratoriumMonths(product.getMoratoriumMonths());
        terms.setMoratoriumMode(mode);
        terms.setEmi(quote.emi());
        terms.setTotalInterest(quote.totalInterest());
        terms.setTotalPayment(quote.totalPayment());
        return terms;
    }

    // ------------------------------------------------------------------ read

    public List<CreditApplication> listForCitizen(String userId) {
        return applications.findByUserIdOrderByCreatedAtDesc(userId);
    }

    /**
     * Mongo ids are guessable and there is no per-document ACL at the
     * repository layer, so ownership is re-checked on every read — the same
     * convention ApplicationController already follows.
     */
    public CreditApplication getForCitizen(String userId, String applicationId) {
        CreditApplication application = applications.findById(applicationId)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Application not found"));
        if (!application.getUserId().equals(userId)) {
            // Deliberately the same message as a genuine miss: confirming the id
            // exists would leak that someone else holds it.
            throw new TransitionException(Failure.NOT_FOUND, "Application not found");
        }
        return application;
    }

    public List<CreditApplication> queueForPartner(String partnerId, CreditApplicationStatus status) {
        return status == null
                ? applications.findByAssignedPartnerIdOrderBySubmittedAtDesc(partnerId)
                : applications.findByAssignedPartnerIdAndStatusOrderBySubmittedAtDesc(partnerId, status);
    }

    // ------------------------------------------------------------ transition

    /**
     * The single gate for every status change.
     *
     * @param actorRole role recorded in the history entry, e.g. CITIZEN or BRANCH_REP
     */
    public CreditApplication transition(CreditApplication application,
                                        CreditApplicationStatus next,
                                        String actorUserId,
                                        String actorRole,
                                        ReasonCode reasonCode,
                                        String note,
                                        List<String> requestedDocuments) {

        CreditApplicationStatus current = application.getStatus();
        if (next == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "status is required");
        }
        if (current == next) {
            throw new TransitionException(Failure.CONFLICT,
                    "Application is already " + next.wireName());
        }
        if (!current.canMoveTo(next)) {
            throw new TransitionException(Failure.CONFLICT, describeRefusal(current, next));
        }

        // A negative outcome without a reason is exactly the "rejected, reason
        // blank" screen this module is meant to stop producing.
        if (next == CreditApplicationStatus.REJECTED && reasonCode == null) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "reasonCode is required when rejecting an application");
        }
        if (next == CreditApplicationStatus.MISSING_DOCS
                && (requestedDocuments == null || requestedDocuments.isEmpty())) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "requestedDocuments must name at least one document when asking for more");
        }

        if (next == CreditApplicationStatus.SUBMITTED) {
            // A submitted application with no branch attached lands in nobody's
            // queue. It would sit at "submitted" forever looking like progress,
            // which is worse for the citizen than being told to pick a branch.
            if (application.getAssignedPartnerId() == null
                    || application.getAssignedPartnerId().isBlank()) {
                throw new TransitionException(Failure.BAD_REQUEST,
                        "Choose the branch you want to apply through before submitting — "
                                + "otherwise there is no one to receive this application.");
            }
            application.setSubmittedAt(LocalDateTime.now());
        }
        if (next == CreditApplicationStatus.MISSING_DOCS) {
            application.setMissingDocuments(new ArrayList<>(requestedDocuments));
        }
        if (next == CreditApplicationStatus.UNDER_VERIFICATION) {
            // Coming back from missing_docs means the ask was answered.
            application.setMissingDocuments(new ArrayList<>());
        }

        application.setStatus(next);
        application.setUpdatedAt(LocalDateTime.now());
        application.getStatusHistory().add(
                entry(next, actorUserId, actorRole, reasonCode, note, requestedDocuments));

        CreditApplication saved = applications.save(application);

        // After the save, deliberately. The transition is a fact once it is
        // persisted; a messaging failure must not undo it, and the notifier
        // swallows its own errors for the same reason.
        if (notifier != null) {
            notifier.onStatusChanged(saved, next);
        }
        return saved;
    }

    private static String describeRefusal(CreditApplicationStatus current, CreditApplicationStatus next) {
        if (current.isTerminal()) {
            return "This application is closed (" + current.wireName() + ") and cannot be reopened";
        }
        String allowed = current.allowedNext().stream()
                .map(CreditApplicationStatus::wireName)
                .sorted()
                .reduce((a, b) -> a + ", " + b)
                .orElse("none");
        return "Cannot move from " + current.wireName() + " to " + next.wireName()
                + " — allowed next: " + allowed;
    }

    private static CreditApplication.StatusEntry entry(CreditApplicationStatus status, String byUserId,
                                                       String byRole, ReasonCode reasonCode, String note,
                                                       List<String> requestedDocuments) {
        CreditApplication.StatusEntry e = new CreditApplication.StatusEntry();
        e.setStatus(status);
        e.setAt(LocalDateTime.now());
        e.setByUserId(byUserId);
        e.setByRole(byRole);
        e.setReasonCode(reasonCode);
        e.setNote(note);
        e.setRequestedDocuments(requestedDocuments == null ? null : List.copyOf(requestedDocuments));
        return e;
    }

    // -------------------------------------------------------------- assignment

    /**
     * Records which Channel Partner branch will work this file.
     *
     * There is no auto-assignment, and that is deliberate. NSFDC's channel
     * partner roster is not publicly obtainable, so picking a branch on the
     * citizen's behalf would mean inventing one — the branch would have no
     * idea the application exists. The citizen chooses a real branch from the
     * locator; this validates that the choice can actually process the scheme.
     *
     * The check is one-sided on purpose. We refuse only what is provably
     * wrong: a Public Sector Bank cannot deliver an NBFC-MFI-only scheme, and
     * sending someone there wastes a trip they may have paid for. An
     * undetermined branch type is allowed through — "we can't tell what this
     * branch is" is not grounds to block a citizen from applying.
     */
    public CreditApplication assignPartner(CreditApplication application, String partnerId,
                                           String partnerName, ChannelPartnerType partnerType) {
        if (partnerId == null || partnerId.isBlank()) {
            throw new TransitionException(Failure.BAD_REQUEST, "partnerId is required");
        }
        if (application.getStatus() != CreditApplicationStatus.DRAFT) {
            // Once a rep is working the file, moving it out from under them
            // would strand their queue and their decisions.
            throw new TransitionException(Failure.CONFLICT,
                    "The branch can only be changed while the application is still a draft "
                            + "(this one is " + application.getStatus().wireName() + ")");
        }

        rejectProvablyWrongChannel(application, partnerType);

        application.setAssignedPartnerId(partnerId);
        application.setAssignedPartnerName(partnerName);
        application.setAssignedPartnerType(partnerType);
        application.setUpdatedAt(LocalDateTime.now());
        return applications.save(application);
    }

    private void rejectProvablyWrongChannel(CreditApplication application, ChannelPartnerType partnerType) {
        if (partnerType == null || partnerType == ChannelPartnerType.UNCLASSIFIED) {
            return; // we don't know what this branch is, so we don't get to refuse it
        }
        CreditProduct product = products.findById(application.getProductId()).orElse(null);
        if (product == null || product.getChannelPartnerTypes() == null
                || product.getChannelPartnerTypes().isEmpty()) {
            return; // no channel data for the scheme — same rule
        }
        if (!product.getChannelPartnerTypes().contains(partnerType)) {
            String canDeliver = product.getChannelPartnerTypes().stream()
                    .map(ChannelPartnerType::label)
                    .reduce((a, b) -> a + ", " + b)
                    .orElse("");
            throw new TransitionException(Failure.BAD_REQUEST,
                    product.getName() + " is not offered by a " + partnerType.label()
                            + ". It is delivered through: " + canDeliver + ".");
        }
    }

    public Optional<CreditApplication> findById(String id) {
        return applications.findById(id);
    }

    // ------------------------------------------------------------------ DTOs

    public record CreateApplicationRequest(
            String productId,
            Long estimatedCost,
            Long annualIncome,
            String category,
            Integer tenureMonths,
            MoratoriumMode moratoriumMode,
            VerificationMode verificationMode,
            String partnerId,
            String partnerName,
            ChannelPartnerType partnerType) {
    }

    /** Picking, or changing, the branch a draft will be sent to. */
    public record PartnerSelectionRequest(
            String partnerId,
            String partnerName,
            ChannelPartnerType partnerType) {
    }
}

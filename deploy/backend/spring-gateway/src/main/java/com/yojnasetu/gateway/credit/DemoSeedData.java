package com.yojnasetu.gateway.credit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * Populates a demo branch and one application per status, so a queue, a
 * timeline, and a dashboard have something in them the first time anyone
 * opens the app.
 *
 * OFF by default, unlike {@link CreditProductSeeder}. That seeder writes
 * reference data safe in any environment; this one writes a fictional citizen
 * with fictional documents and a login whose password is printed to the log.
 * Booting a production instance with this on would be a real data and
 * security problem, so it requires {@code app.demo-seed.enabled=true} rather
 * than running unconditionally.
 *
 * Insert-only and keyed on fixed ids, so re-running never duplicates or
 * resets anything a demo session has already changed — a rep who moves
 * DEMO-APP-2 from missing_docs to under_verification during a walkthrough
 * keeps that state across a restart.
 */
@Component
public class DemoSeedData implements CommandLineRunner {

    private static final Logger LOG = LoggerFactory.getLogger(DemoSeedData.class);

    private static final String DEMO_CITIZEN_ID = "demo-citizen-1";
    private static final String PARTNER_ID = "demo-partner-1";
    private static final String PARTNER_NAME = "Bank of Baroda, Connaught Place";
    private static final String REP_ID = "DEMO-CP-001";
    private static final String REP_PASSWORD = "demo-password-1";

    // An assist-only helper too, because the assisted path is the one most
    // applicants will actually use and a demo that only ever shows a bank rep
    // signing in makes it look like self-serve is the whole product.
    private static final String CSC_ID = "DEMO-CSC-001";
    private static final String CSC_PASSWORD = "demo-password-2";

    @Value("${app.demo-seed.enabled:false}")
    private boolean enabled;

    private final CreditApplicationRepository applications;
    private final BranchRepRepository branchReps;
    private final CreditProductRepository products;

    public DemoSeedData(CreditApplicationRepository applications,
                        BranchRepRepository branchReps,
                        CreditProductRepository products) {
        this.applications = applications;
        this.branchReps = branchReps;
        this.products = products;
    }

    @Override
    public void run(String... args) {
        if (!enabled) {
            return;
        }

        CreditProduct scheme = products.findById("micro-finance").orElse(null);
        if (scheme == null) {
            // CreditProductSeeder always runs first in bean-init order the way
            // Spring processes CommandLineRunners here, but a missing scheme
            // must fail loudly rather than produce applications with no
            // product to point at.
            LOG.error("Demo seed skipped: micro-finance product not found. "
                    + "Has CreditProductSeeder run?");
            return;
        }

        seedRep();
        seedCscHelper();
        int inserted = seedApplications(scheme);
        if (inserted > 0) {
            LOG.info("Demo seed: inserted {} application(s). Branch-rep login: {} / {}. "
                            + "CSC helper login: {} / {}",
                    inserted, REP_ID, REP_PASSWORD, CSC_ID, CSC_PASSWORD);
        }
    }

    private void seedRep() {
        if (branchReps.findByRepId(REP_ID).isPresent()) {
            return;
        }
        BranchRep rep = new BranchRep();
        rep.setRepId(REP_ID);
        rep.setPasswordHash(new BCryptPasswordEncoder().encode(REP_PASSWORD));
        rep.setName("Demo Representative");
        rep.setRepType(RepType.BANK_BRANCH);
        rep.setPartnerId(PARTNER_ID);
        rep.setPartnerName(PARTNER_NAME);
        rep.setActive(true);
        rep.setMustResetPassword(false); // a demo login should not interrupt the walkthrough
        rep.setCreatedAt(LocalDateTime.now());
        branchReps.save(rep);
    }

    /**
     * A CSC operator: no partnerId, no decision authority, and no access to
     * anything until a citizen authorizes them for a specific application.
     * Seeded without any authorization on purpose — logging in and seeing an
     * empty worklist is the honest demonstration that access comes from the
     * citizen, not from holding an account.
     */
    private void seedCscHelper() {
        if (branchReps.findByRepId(CSC_ID).isPresent()) {
            return;
        }
        BranchRep helper = new BranchRep();
        helper.setRepId(CSC_ID);
        helper.setPasswordHash(new BCryptPasswordEncoder().encode(CSC_PASSWORD));
        helper.setName("Demo CSC Operator");
        helper.setRepType(RepType.CSC);
        helper.setOrganisation("CSC — Connaught Place");
        helper.setActive(true);
        helper.setMustResetPassword(false);
        helper.setCreatedAt(LocalDateTime.now());
        branchReps.save(helper);
    }

    private int seedApplications(CreditProduct scheme) {
        int inserted = 0;
        for (Spec spec : specs()) {
            if (applications.existsById(spec.id())) {
                continue;
            }
            applications.save(build(spec, scheme));
            inserted++;
        }
        return inserted;
    }

    /** One entry per CreditApplicationStatus, in the order a real file moves through them. */
    private record Spec(String id, CreditApplicationStatus status, ReasonCode reasonCode,
                        List<String> missingDocs, int daysAgoCreated) {
    }

    private static List<Spec> specs() {
        return List.of(
                new Spec("demo-app-draft", CreditApplicationStatus.DRAFT, null, null, 0),
                new Spec("demo-app-submitted", CreditApplicationStatus.SUBMITTED, null, null, 1),
                new Spec("demo-app-verification", CreditApplicationStatus.UNDER_VERIFICATION, null, null, 3),
                new Spec("demo-app-missing-docs", CreditApplicationStatus.MISSING_DOCS,
                        ReasonCode.DOCUMENTS_INCOMPLETE,
                        List.of("Caste certificate", "Income certificate (current year)"), 4),
                new Spec("demo-app-forwarded", CreditApplicationStatus.FORWARDED, null, null, 6),
                new Spec("demo-app-sanctioned", CreditApplicationStatus.SANCTIONED, null, null, 9),
                new Spec("demo-app-rejected", CreditApplicationStatus.REJECTED,
                        ReasonCode.INCOME_ABOVE_CEILING, null, 5),
                new Spec("demo-app-disbursed", CreditApplicationStatus.DISBURSED, null, null, 20));
    }

    private CreditApplication build(Spec spec, CreditProduct scheme) {
        CreditApplication app = new CreditApplication();
        app.setId(spec.id());
        app.setUserId(DEMO_CITIZEN_ID);
        app.setProductId(scheme.getId());
        app.setProductCode(scheme.getCode());
        app.setProductName(scheme.getName());

        long cost = 100_000L;
        long loanAmount = Math.min(Math.round(cost * (scheme.getCoveragePct() / 100.0)),
                scheme.getMaxLoanAmount());

        app.setEstimatedCost(cost);
        app.setRequestedAmount(loanAmount);
        app.setMarginMoney(cost - loanAmount);
        app.setDeclaredAnnualIncome(300_000L);
        app.setDeclaredCategory("sc");
        app.setVerificationMode(VerificationMode.MANUAL);

        CreditApplication.QuotedTerms terms = new CreditApplication.QuotedTerms();
        terms.setInterestRate(scheme.getInterestRate());
        terms.setTenureMonths(scheme.getMaxTenureMonths());
        terms.setMoratoriumMonths(scheme.getMoratoriumMonths());
        terms.setMoratoriumMode(MoratoriumMode.CAPITALISE);
        var quote = EmiCalculator.calculate(loanAmount, scheme.getInterestRate(),
                scheme.getMaxTenureMonths(), scheme.getMoratoriumMonths(), MoratoriumMode.CAPITALISE);
        terms.setEmi(quote.emi());
        terms.setTotalInterest(quote.totalInterest());
        terms.setTotalPayment(quote.totalPayment());
        app.setQuotedTerms(terms);

        app.setStatus(spec.status());
        app.setMissingDocuments(spec.missingDocs() == null ? new ArrayList<>() : spec.missingDocs());

        LocalDateTime created = LocalDateTime.now().minusDays(spec.daysAgoCreated());
        app.setCreatedAt(created);
        app.setUpdatedAt(LocalDateTime.now());
        app.setStatusHistory(buildHistory(spec, created));

        if (spec.status() != CreditApplicationStatus.DRAFT) {
            app.setSubmittedAt(created.plusHours(1));
            app.setAssignedPartnerId(PARTNER_ID);
            app.setAssignedPartnerName(PARTNER_NAME);
            app.setAssignedPartnerType(ChannelPartnerType.PSB);
        }

        return app;
    }

    /**
     * A history that walks the SAME path the real state machine allows,
     * rather than jumping straight to the target status. A demo screen that
     * only ever showed the current status would not exercise the timeline UI
     * at all, which is the point of seeding this.
     */
    private List<CreditApplication.StatusEntry> buildHistory(Spec spec, LocalDateTime created) {
        List<CreditApplicationStatus> path = pathTo(spec.status());
        List<CreditApplication.StatusEntry> history = new ArrayList<>();

        for (int i = 0; i < path.size(); i++) {
            CreditApplicationStatus status = path.get(i);
            CreditApplicationStatus previous = i == 0 ? null : path.get(i - 1);

            // Citizen acts: opening a draft, submitting it, or answering a
            // document request. Everything else — a rep moving the file
            // forward — is recorded with no citizen id, matching how the real
            // controllers populate a rep-initiated StatusEntry.
            boolean byCitizen = status == CreditApplicationStatus.DRAFT
                    || status == CreditApplicationStatus.SUBMITTED
                    || (status == CreditApplicationStatus.UNDER_VERIFICATION
                        && previous == CreditApplicationStatus.MISSING_DOCS);

            CreditApplication.StatusEntry entry = new CreditApplication.StatusEntry();
            entry.setStatus(status);
            entry.setAt(created.plusHours(i));
            entry.setByUserId(byCitizen ? DEMO_CITIZEN_ID : null);
            entry.setByRole(byCitizen ? "CITIZEN" : "BRANCH_REP");
            if (status == spec.status()) {
                entry.setReasonCode(spec.reasonCode());
                entry.setRequestedDocuments(spec.missingDocs());
            }
            history.add(entry);
        }
        return history;
    }

    /** The legal route from DRAFT to the target status, per CreditApplicationStatus. */
    private static List<CreditApplicationStatus> pathTo(CreditApplicationStatus target) {
        return switch (target) {
            case DRAFT -> List.of(CreditApplicationStatus.DRAFT);
            case SUBMITTED -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED);
            case UNDER_VERIFICATION -> List.of(CreditApplicationStatus.DRAFT,
                    CreditApplicationStatus.SUBMITTED, CreditApplicationStatus.UNDER_VERIFICATION);
            case MISSING_DOCS -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED,
                    CreditApplicationStatus.UNDER_VERIFICATION, CreditApplicationStatus.MISSING_DOCS);
            case FORWARDED -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED,
                    CreditApplicationStatus.UNDER_VERIFICATION, CreditApplicationStatus.FORWARDED);
            case SANCTIONED -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED,
                    CreditApplicationStatus.UNDER_VERIFICATION, CreditApplicationStatus.FORWARDED,
                    CreditApplicationStatus.SANCTIONED);
            case DISBURSED -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED,
                    CreditApplicationStatus.UNDER_VERIFICATION, CreditApplicationStatus.FORWARDED,
                    CreditApplicationStatus.SANCTIONED, CreditApplicationStatus.DISBURSED);
            // A rejection can happen from several points; this demo rejects
            // after verification, the most common real case.
            case REJECTED -> List.of(CreditApplicationStatus.DRAFT, CreditApplicationStatus.SUBMITTED,
                    CreditApplicationStatus.UNDER_VERIFICATION, CreditApplicationStatus.REJECTED);
        };
    }
}

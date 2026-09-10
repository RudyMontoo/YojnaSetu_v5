package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.CreateApplicationRequest;
import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CreditApplicationServiceTest {

    private static final String CITIZEN = "citizen-1";
    private static final String PRODUCT = "micro-finance";

    private CreditApplicationRepository applications;
    private CreditProductRepository products;
    private CreditApplicationService service;

    @BeforeEach
    void setUp() {
        applications = mock(CreditApplicationRepository.class);
        products = mock(CreditProductRepository.class);
        service = new CreditApplicationService(applications, products);

        when(products.findById(PRODUCT)).thenReturn(Optional.of(microFinance()));
        when(applications.findByUserIdAndProductId(anyString(), anyString())).thenReturn(List.of());
        // Persisting is not what these tests are about — hand the entity straight back.
        when(applications.save(any(CreditApplication.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
    }

    private static CreditProduct microFinance() {
        CreditProduct p = new CreditProduct();
        p.setId(PRODUCT);
        p.setCode("MFS");
        p.setName("Micro Finance Scheme (MFS)");
        p.setType("micro");
        p.setProjectType("small");
        // NSFDC's real Micro Finance terms: units up to ₹1.40 lakh, loan up to
        // ₹1.25 lakh. The two ceilings are different numbers.
        p.setUnitCostFloor(null);
        p.setUnitCostCeiling(140_000L);
        p.setMaxLoanAmount(125_000);
        p.setInterestRate(6.5);
        p.setMoratoriumMonths(3);
        p.setMaxTenureMonths(36);
        p.setCoveragePct(90);
        p.setMaxAnnualIncome(500_000);
        p.setCategories(List.of("sc"));
        // Matches CreditProductSeeder. Without this the channel check silently
        // short-circuits — the same fixture-drift that once hid a real bug.
        p.setChannelPartnerTypes(List.of(ChannelPartnerType.SCA, ChannelPartnerType.PSB,
                ChannelPartnerType.RRB, ChannelPartnerType.COOPERATIVE));
        p.setActive(true);
        return p;
    }

    private static CreateApplicationRequest request(long cost) {
        return new CreateApplicationRequest(PRODUCT, cost, 300_000L, "sc", null, null, null, null, null, null);
    }

    private CreditApplication draft() {
        return service.create(CITIZEN, request(100_000));
    }

    // ---------------------------------------------------------------- create

    @Test
    void opensADraftWithTheTermsTheCitizenWasQuoted() {
        CreditApplication application = draft();

        assertEquals(CreditApplicationStatus.DRAFT, application.getStatus());
        assertEquals(90_000L, application.getRequestedAmount());
        assertEquals(10_000L, application.getMarginMoney());
        assertEquals("MFS", application.getProductCode());
        assertEquals(1, application.getStatusHistory().size());
        assertEquals("CITIZEN", application.getStatusHistory().get(0).getByRole());
    }

    @Test
    void snapshotsRepaymentTermsSoALaterRateChangeCannotRewriteHistory() {
        CreditApplication.QuotedTerms terms = draft().getQuotedTerms();

        assertEquals(6.5, terms.getInterestRate());
        assertEquals(3, terms.getMoratoriumMonths());
        assertEquals(36, terms.getTenureMonths());
        assertEquals(MoratoriumMode.CAPITALISE, terms.getMoratoriumMode());
        // Moratorium interest is inside these figures — the whole point of the fix.
        assertTrue(terms.getTotalPayment() > 90_000);
        assertTrue(terms.getEmi() > 0);
    }

    @Test
    void refusesASecondLiveApplicationForTheSameScheme() {
        CreditApplication inFlight = new CreditApplication();
        inFlight.setStatus(CreditApplicationStatus.UNDER_VERIFICATION);
        when(applications.findByUserIdAndProductId(CITIZEN, PRODUCT)).thenReturn(List.of(inFlight));

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.create(CITIZEN, request(100_000)));
        assertEquals(Failure.CONFLICT, thrown.failure());
    }

    @Test
    void letsARejectedApplicantTryAgain() {
        // The behaviour the welfare Application model's unique index forbids
        // outright: fix the paperwork, apply again.
        CreditApplication closed = new CreditApplication();
        closed.setStatus(CreditApplicationStatus.REJECTED);
        when(applications.findByUserIdAndProductId(CITIZEN, PRODUCT)).thenReturn(List.of(closed));

        assertEquals(CreditApplicationStatus.DRAFT, service.create(CITIZEN, request(100_000)).getStatus());
    }

    @Test
    void refusesAVerificationModeThatIsNotBuiltYet() {
        CreateApplicationRequest digilocker = new CreateApplicationRequest(
                PRODUCT, 100_000L, 300_000L, "sc", null, null, VerificationMode.DIGILOCKER, null, null, null);

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.create(CITIZEN, digilocker));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("not available yet"));
    }

    @Test
    void refusesAProjectAboveTheSchemesUnitCostBand() {
        // ₹2 lakh is past Micro Finance's ₹1.40 lakh unit-cost ceiling — that's
        // a different scheme's territory, not a margin-money shortfall.
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.create(CITIZEN, request(200_000)));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("₹1,40,000"));
    }

    @Test
    void capsTheLoanAtTheSchemeCeilingAndBooksTheRestAsMarginMoney() {
        // A ₹1.40 lakh project: 90% is ₹1.26 lakh, but the scheme lends at most
        // ₹1.25 lakh — so margin money is ₹15,000, not ₹14,000.
        CreditApplication application = service.create(CITIZEN, request(140_000));

        assertEquals(125_000L, application.getRequestedAmount());
        assertEquals(15_000L, application.getMarginMoney());
    }

    @Test
    void rejectsAnUnknownProduct() {
        when(products.findById("nope")).thenReturn(Optional.empty());
        CreateApplicationRequest bad = new CreateApplicationRequest(
                "nope", 100_000L, 300_000L, "sc", null, null, null, null, null, null);

        assertEquals(Failure.NOT_FOUND,
                assertThrows(TransitionException.class, () -> service.create(CITIZEN, bad)).failure());
    }

    @Test
    void rejectsATenureLongerThanTheSchemeAllows() {
        CreateApplicationRequest tooLong = new CreateApplicationRequest(
                PRODUCT, 100_000L, 300_000L, "sc", 120, null, null, null, null, null);

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.create(CITIZEN, tooLong)).failure());
    }

    // ------------------------------------------------------------ transition

    @Test
    void submittingStampsTheSubmissionTimeAndRecordsWhoActed() {
        CreditApplication submitted = service.transition(assignedDraft(),
                CreditApplicationStatus.SUBMITTED, CITIZEN, "CITIZEN", null, null, null);

        assertEquals(CreditApplicationStatus.SUBMITTED, submitted.getStatus());
        assertTrue(submitted.getSubmittedAt() != null);
        assertEquals(CITIZEN, submitted.getStatusHistory().get(1).getByUserId());
    }

    @Test
    void refusesAnIllegalMoveAndSaysWhatIsAllowed() {
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.transition(draft(), CreditApplicationStatus.DISBURSED,
                        "rep-1", "BRANCH_REP", null, null, null));

        assertEquals(Failure.CONFLICT, thrown.failure());
        assertTrue(thrown.getMessage().contains("allowed next: submitted"));
    }

    @Test
    void refusesToReopenAClosedFile() {
        CreditApplication closed = draft();
        closed.setStatus(CreditApplicationStatus.DISBURSED);

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.transition(closed, CreditApplicationStatus.UNDER_VERIFICATION,
                        "rep-1", "BRANCH_REP", null, null, null));
        assertTrue(thrown.getMessage().contains("closed"));
    }

    @Test
    void refusesARepeatOfTheCurrentStatus() {
        assertEquals(Failure.CONFLICT, assertThrows(TransitionException.class,
                () -> service.transition(draft(), CreditApplicationStatus.DRAFT,
                        CITIZEN, "CITIZEN", null, null, null)).failure());
    }

    @Test
    void willNotRejectAnApplicationWithoutARecordedReason() {
        CreditApplication submitted = service.transition(assignedDraft(),
                CreditApplicationStatus.SUBMITTED, CITIZEN, "CITIZEN", null, null, null);

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.transition(submitted, CreditApplicationStatus.REJECTED,
                        "rep-1", "BRANCH_REP", null, "no reason given", null));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("reasonCode"));
    }

    @Test
    void recordsTheReasonCodeOnARejection() {
        CreditApplication submitted = service.transition(assignedDraft(),
                CreditApplicationStatus.SUBMITTED, CITIZEN, "CITIZEN", null, null, null);

        CreditApplication rejected = service.transition(submitted, CreditApplicationStatus.REJECTED,
                "rep-1", "BRANCH_REP", ReasonCode.DOCUMENTS_ILLEGIBLE, "Income certificate unreadable", null);

        CreditApplication.StatusEntry last = rejected.getStatusHistory()
                .get(rejected.getStatusHistory().size() - 1);
        assertEquals(ReasonCode.DOCUMENTS_ILLEGIBLE, last.getReasonCode());
        assertEquals("BRANCH_REP", last.getByRole());
    }

    @Test
    void willNotAskForDocumentsWithoutNamingThem() {
        CreditApplication verifying = underVerification();

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.transition(verifying, CreditApplicationStatus.MISSING_DOCS,
                        "rep-1", "BRANCH_REP", ReasonCode.DOCUMENTS_INCOMPLETE, "send more", List.of()));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
    }

    @Test
    void carriesTheDocumentRequestOntoTheApplication() {
        CreditApplication asked = service.transition(underVerification(),
                CreditApplicationStatus.MISSING_DOCS, "rep-1", "BRANCH_REP",
                ReasonCode.DOCUMENTS_INCOMPLETE, null, List.of("Caste certificate", "Income proof"));

        assertEquals(List.of("Caste certificate", "Income proof"), asked.getMissingDocuments());
    }

    @Test
    void clearsTheDocumentRequestOnceVerificationResumes() {
        CreditApplication asked = service.transition(underVerification(),
                CreditApplicationStatus.MISSING_DOCS, "rep-1", "BRANCH_REP",
                ReasonCode.DOCUMENTS_INCOMPLETE, null, List.of("Caste certificate"));

        CreditApplication resumed = service.transition(asked,
                CreditApplicationStatus.UNDER_VERIFICATION, CITIZEN, "CITIZEN", null, null, null);

        assertTrue(resumed.getMissingDocuments().isEmpty());
    }

    private CreditApplication underVerification() {
        CreditApplication submitted = service.transition(assignedDraft(),
                CreditApplicationStatus.SUBMITTED, CITIZEN, "CITIZEN", null, null, null);
        return service.transition(submitted, CreditApplicationStatus.UNDER_VERIFICATION,
                "rep-1", "BRANCH_REP", null, null, null);
    }

    // ------------------------------------------------- partner assignment

    private CreditApplication assignedDraft() {
        return service.assignPartner(draft(), "partner-7", "SBI Kanpur Nagar", ChannelPartnerType.PSB);
    }

    @Test
    void willNotSubmitAnApplicationWithNoBranchToReceiveIt() {
        // Without a branch it lands in nobody's queue and sits at "submitted"
        // forever looking like progress — worse than being told to pick one.
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.transition(draft(), CreditApplicationStatus.SUBMITTED,
                        CITIZEN, "CITIZEN", null, null, null));

        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("Choose the branch"));
    }

    @Test
    void recordsThePartnerTypeBecauseTheRateDependsOnIt() {
        CreditApplication assigned = assignedDraft();

        assertEquals("partner-7", assigned.getAssignedPartnerId());
        assertEquals("SBI Kanpur Nagar", assigned.getAssignedPartnerName());
        assertEquals(ChannelPartnerType.PSB, assigned.getAssignedPartnerType());
    }

    @Test
    void refusesABranchThatProvablyCannotDeliverTheScheme() {
        // Micro Finance runs through SCA/PSB/RRB/co-operatives. Sending someone
        // to an NBFC-MFI for it wastes a trip they may have paid for.
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.assignPartner(draft(), "mfi-1", "Some MFI", ChannelPartnerType.NBFC_MFI));

        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("is delivered through"),
                () -> "message should name the right channels, got: " + thrown.getMessage());
    }

    @Test
    void allowsABranchWhoseTypeWeCouldNotDetermine() {
        // "We can't tell what this branch is" is not grounds to block a citizen
        // from applying — only a provable mismatch is.
        assertEquals(ChannelPartnerType.UNCLASSIFIED,
                service.assignPartner(draft(), "x", "Some Bank", ChannelPartnerType.UNCLASSIFIED)
                        .getAssignedPartnerType());

        assertNull(service.assignPartner(draft(), "x", "Some Bank", null).getAssignedPartnerType());
    }

    @Test
    void refusesToMoveTheBranchOnceARepIsWorkingTheFile() {
        CreditApplication submitted = service.transition(assignedDraft(),
                CreditApplicationStatus.SUBMITTED, CITIZEN, "CITIZEN", null, null, null);

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.assignPartner(submitted, "other", "Other Branch", ChannelPartnerType.PSB));
        assertEquals(Failure.CONFLICT, thrown.failure());
    }

    @Test
    void stillRequiresAPartnerId() {
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.assignPartner(draft(), "  ", "Nameless", ChannelPartnerType.PSB)).failure());
    }

    // ------------------------------------------------------------------ read

    @Test
    void hidesAnotherCitizensApplicationBehindANotFound() {
        CreditApplication someoneElses = new CreditApplication();
        someoneElses.setId("app-9");
        someoneElses.setUserId("citizen-2");
        when(applications.findById("app-9")).thenReturn(Optional.of(someoneElses));

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.getForCitizen(CITIZEN, "app-9"));
        // Not FORBIDDEN — confirming the id exists would leak that someone holds it.
        assertEquals(Failure.NOT_FOUND, thrown.failure());
        assertEquals("Application not found", thrown.getMessage());
    }

    @Test
    void assignsAPartnerBranchToWorkTheFile() {
        CreditApplication assigned = service.assignPartner(draft(), "partner-7", "SBI Kanpur Nagar", ChannelPartnerType.PSB);

        assertEquals("partner-7", assigned.getAssignedPartnerId());
        assertEquals("SBI Kanpur Nagar", assigned.getAssignedPartnerName());
    }

    @Test
    void leavesAnUnassignedApplicationWithoutAPartner() {
        assertNull(draft().getAssignedPartnerId());
    }
}

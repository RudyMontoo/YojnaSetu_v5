package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import com.yojnasetu.gateway.service.EmailService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Base64;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class BranchRepApplicationServiceTest {

    /**
     * The real cipher on a throwaway key, not a stub — same reasoning as
     * LoanDocumentServiceTest: encryption is the point, so the round-trip
     * should be exercised for real.
     */
    private static final FieldEncryptionService CIPHER = new FieldEncryptionService(
            Base64.getEncoder().encodeToString(new byte[32]));

    private BranchRepApplicationRepository applications;
    private BranchRepRepository branchReps;
    private UserRepository users;
    private EmailService emailService;
    private BranchRepApplicationService service;

    @BeforeEach
    void setUp() {
        applications = mock(BranchRepApplicationRepository.class);
        branchReps = mock(BranchRepRepository.class);
        users = mock(UserRepository.class);
        emailService = mock(EmailService.class);
        when(applications.save(any(BranchRepApplication.class))).thenAnswer(inv -> inv.getArgument(0));
        when(applications.findFirstByUserIdOrderByCreatedAtDesc(anyString())).thenReturn(Optional.empty());
        when(branchReps.save(any(BranchRep.class))).thenAnswer(inv -> inv.getArgument(0));
        when(branchReps.findByRepId(anyString())).thenReturn(Optional.empty());
        service = new BranchRepApplicationService(applications, branchReps, users, CIPHER, emailService);
    }

    private static BranchRepApplicationService.ApplyRequest validRequest(RepType repType) {
        return new BranchRepApplicationService.ApplyRequest(
                "Sita Devi", "9876543210", "234123412346", "ABCDE1234F",
                repType, "CSC-UP-0142", "CSC registration certificate");
    }

    // ----------------------------------------------------------------- apply

    @Test
    void acceptsAValidCscApplication() {
        BranchRepApplication saved = service.apply("citizen-1", validRequest(RepType.CSC));

        assertEquals("pending", saved.getStatus());
        assertEquals(RepType.CSC, saved.getRepType());
        assertEquals("CSC-UP-0142", saved.getOrganisation());
        assertTrue(saved.isAadhaarVerified());
        assertEquals("XXXX-XXXX-2346", saved.getAadhaarMasked());
        // PII must not be stored in the clear.
        assertFalse(saved.getFullName().contains("Sita Devi"));
        assertEquals("Sita Devi", CIPHER.decrypt(saved.getFullName()));
        assertEquals("ABCDE1234F", CIPHER.decrypt(saved.getPan()));
    }

    @Test
    void refusesABankBranchSelfApplication() {
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.apply("citizen-1", validRequest(RepType.BANK_BRANCH)));

        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("appointed by their lending institution"));
    }

    @Test
    void refusesAMalformedPan() {
        BranchRepApplicationService.ApplyRequest req = new BranchRepApplicationService.ApplyRequest(
                "Sita Devi", "9876543210", "234123412346", "NOT-A-PAN",
                RepType.CSC, "CSC-UP-0142", null);

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.apply("citizen-1", req)).failure());
    }

    @Test
    void refusesAnAadhaarThatIsNotTwelveDigits() {
        BranchRepApplicationService.ApplyRequest req = new BranchRepApplicationService.ApplyRequest(
                "Sita Devi", "9876543210", "12345", "ABCDE1234F",
                RepType.NGO_SHG, "Nari Shakti SHG", null);

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.apply("citizen-1", req)).failure());
    }

    @Test
    void refusesWhenOrganisationIsMissing() {
        BranchRepApplicationService.ApplyRequest req = new BranchRepApplicationService.ApplyRequest(
                "Sita Devi", "9876543210", "234123412346", "ABCDE1234F",
                RepType.FIELD_AGENT, "  ", null);

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.apply("citizen-1", req)).failure());
    }

    @Test
    void refusesADuplicateApplicationWhileOneIsPending() {
        BranchRepApplication existing = new BranchRepApplication();
        existing.setStatus("pending");
        when(applications.findFirstByUserIdOrderByCreatedAtDesc("citizen-1")).thenReturn(Optional.of(existing));

        assertEquals(Failure.CONFLICT,
                assertThrows(TransitionException.class,
                        () -> service.apply("citizen-1", validRequest(RepType.CSC))).failure());
    }

    @Test
    void allowsReapplyingAfterAPriorRejection() {
        BranchRepApplication existing = new BranchRepApplication();
        existing.setStatus("rejected");
        when(applications.findFirstByUserIdOrderByCreatedAtDesc("citizen-1")).thenReturn(Optional.of(existing));

        BranchRepApplication saved = service.apply("citizen-1", validRequest(RepType.CSC));
        assertEquals("pending", saved.getStatus());
    }

    // --------------------------------------------------------------- approve

    @Test
    void approvingMintsARepIdPrefixedByType() {
        BranchRepApplication application = service.apply("citizen-1", validRequest(RepType.NGO_SHG));
        application.setId("app-1");
        application.setUserId("citizen-1");
        when(applications.findById("app-1")).thenReturn(Optional.of(application));
        when(users.findById("citizen-1")).thenReturn(Optional.of(userWithEmail("sita@example.com")));

        BranchRepApplicationService.ApprovalResult result = service.approve("app-1", "admin-1");

        assertTrue(result.repId().startsWith("NGO-"));
        assertEquals("sita@example.com", result.emailedTo());
        verify(emailService).sendBranchRepCredentials("sita@example.com", "Sita Devi",
                RepType.NGO_SHG.label(), result.repId(), result.tempPassword());
        verify(branchReps).save(any(BranchRep.class));
    }

    @Test
    void approvingWithoutAKnownEmailStillMintsTheAccount() {
        BranchRepApplication application = service.apply("citizen-1", validRequest(RepType.CSC));
        application.setId("app-1");
        application.setUserId("citizen-1");
        when(applications.findById("app-1")).thenReturn(Optional.of(application));
        when(users.findById("citizen-1")).thenReturn(Optional.empty());

        BranchRepApplicationService.ApprovalResult result = service.approve("app-1", "admin-1");

        assertEquals(null, result.emailedTo());
        verify(emailService, never()).sendBranchRepCredentials(anyString(), anyString(), anyString(), anyString(), anyString());
    }

    @Test
    void refusesToApproveTwice() {
        BranchRepApplication application = service.apply("citizen-1", validRequest(RepType.CSC));
        application.setId("app-1");
        application.setUserId("citizen-1");
        application.setStatus("approved");
        when(applications.findById("app-1")).thenReturn(Optional.of(application));

        assertEquals(Failure.CONFLICT,
                assertThrows(TransitionException.class, () -> service.approve("app-1", "admin-1")).failure());
    }

    @Test
    void reportsApprovingAMissingApplicationAsNotFound() {
        when(applications.findById("gone")).thenReturn(Optional.empty());
        assertEquals(Failure.NOT_FOUND,
                assertThrows(TransitionException.class, () -> service.approve("gone", "admin-1")).failure());
    }

    // ---------------------------------------------------------------- reject

    @Test
    void rejectMarksTheApplicationRejected() {
        BranchRepApplication application = service.apply("citizen-1", validRequest(RepType.CSC));
        application.setId("app-1");
        when(applications.findById("app-1")).thenReturn(Optional.of(application));

        service.reject("app-1", "admin-1");

        assertEquals("rejected", application.getStatus());
        assertEquals("admin-1", application.getReviewedBy());
    }

    private static User userWithEmail(String email) {
        User u = new User();
        u.setEmail(email);
        return u;
    }
}

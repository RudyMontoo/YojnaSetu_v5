package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * The applicant's copy of the audit trail.
 *
 * What's pinned here is mostly about honesty of the view: that it includes the
 * events an applicant most wants (who opened my documents), that it names
 * people rather than ids, and that a withdrawal is still visible afterwards.
 */
class FileAccessServiceTest {

    private AssistAuthorizationRepository authorizations;
    private LoanDocumentRepository documents;
    private AuditLogRepository auditLogs;
    private BranchRepRepository helpers;
    private FileAccessService service;

    @BeforeEach
    void setUp() {
        authorizations = mock(AssistAuthorizationRepository.class);
        documents = mock(LoanDocumentRepository.class);
        auditLogs = mock(AuditLogRepository.class);
        helpers = mock(BranchRepRepository.class);

        when(authorizations.findByApplicationIdOrderByGrantedAtDesc(anyString())).thenReturn(List.of());
        when(documents.findByApplicationIdOrderByUploadedAtDesc(anyString())).thenReturn(List.of());
        when(auditLogs.findByApplicationIdOrderByAtDesc(anyString())).thenReturn(List.of());
        when(helpers.findById(anyString())).thenReturn(Optional.empty());

        service = new FileAccessService(authorizations, documents, auditLogs, helpers);
    }

    private static CreditApplication application() {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        return a;
    }

    private static AssistAuthorization authorization(LocalDateTime granted, LocalDateTime revoked) {
        AssistAuthorization a = new AssistAuthorization();
        a.setApplicationId("app-1");
        a.setCitizenId("citizen-1");
        a.setHelperId("h-1");
        a.setHelperName("R. Devi");
        a.setHelperType(RepType.CSC);
        a.setHelperOrganisation("CSC Ranchi");
        a.setGrantedAt(granted);
        a.setRevokedAt(revoked);
        return a;
    }

    @Test
    void showsWhoWasLetInAndWhen() {
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1"))
                .thenReturn(List.of(authorization(LocalDateTime.now().minusDays(3), null)));

        List<FileAccessService.AccessEvent> timeline = service.timelineFor(application());

        assertEquals(1, timeline.size());
        assertEquals("assist_granted", timeline.get(0).action());
        assertTrue(timeline.get(0).actor().contains("R. Devi"));
    }

    @Test
    void describesAHelperInWordsNotAnInternalId() {
        // A list of document ids answers the question in form only.
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1"))
                .thenReturn(List.of(authorization(LocalDateTime.now(), null)));

        String actor = service.timelineFor(application()).get(0).actor();

        assertTrue(actor.contains("CSC operator"), () -> "expected a readable type, got: " + actor);
        assertTrue(actor.contains("CSC Ranchi"), () -> "expected the organisation, got: " + actor);
        assertFalse(actor.contains("h-1"), () -> "internal id leaked to the citizen: " + actor);
    }

    @Test
    void aWithdrawalStaysVisibleAfterwards() {
        // The point of keeping the row: "nobody has access now" and "nobody
        // ever had access" must not look the same to the person asking.
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1"))
                .thenReturn(List.of(authorization(
                        LocalDateTime.now().minusDays(3), LocalDateTime.now().minusDays(1))));

        List<String> actions = service.timelineFor(application()).stream()
                .map(FileAccessService.AccessEvent::action).toList();

        assertTrue(actions.contains("assist_granted"));
        assertTrue(actions.contains("assist_revoked"));
    }

    @Test
    void includesWhoOpenedTheDocuments() {
        // The event that exists nowhere else, and the one an applicant handing
        // over a caste certificate most wants to be able to check.
        AuditLog read = AuditLog.forApplication("rep-9", "loan_document_read_by_rep",
                "/api/v2/branch/applications/app-1/documents/d-1", "1.2.3.4", "app-1");
        when(auditLogs.findByApplicationIdOrderByAtDesc("app-1")).thenReturn(List.of(read));

        List<FileAccessService.AccessEvent> timeline = service.timelineFor(application());

        assertEquals(1, timeline.size());
        assertEquals("document_viewed", timeline.get(0).action());
    }

    @Test
    void doesNotDoubleCountUploadsThatTheDocumentRecordAlreadyReports() {
        LoanDocument document = new LoanDocument();
        document.setApplicationId("app-1");
        document.setFilename("caste-certificate.pdf");
        document.setUploadedByUserId("h-1");
        document.setUploadedByRole("CSC");
        document.setUploadedAt(LocalDateTime.now());
        when(documents.findByApplicationIdOrderByUploadedAtDesc("app-1")).thenReturn(List.of(document));
        when(auditLogs.findByApplicationIdOrderByAtDesc("app-1")).thenReturn(List.of(
                AuditLog.forApplication("h-1", "loan_document_upload_by_helper", "/x", "1.2.3.4", "app-1")));

        List<FileAccessService.AccessEvent> timeline = service.timelineFor(application());

        assertEquals(1, timeline.size(), "the upload should appear once, from the document record");
        assertEquals("document_uploaded", timeline.get(0).action());
    }

    @Test
    void callsTheCitizensOwnActionsYouRatherThanNamingThem() {
        CreditApplication app = application();
        CreditApplication.StatusEntry entry = new CreditApplication.StatusEntry();
        entry.setStatus(CreditApplicationStatus.SUBMITTED);
        entry.setAt(LocalDateTime.now());
        entry.setByUserId("citizen-1");
        entry.setByRole("CITIZEN");
        app.setStatusHistory(List.of(entry));

        assertEquals("You", service.timelineFor(app).get(0).actor());
    }

    @Test
    void namesStaffFromTheirAccountRatherThanShowingARawId() {
        BranchRep rep = new BranchRep();
        rep.setId("rep-9");
        rep.setName("A. Kumar");
        rep.setRepType(RepType.BANK_BRANCH);
        rep.setPartnerName("Bank of Baroda, Connaught Place");
        when(helpers.findById("rep-9")).thenReturn(Optional.of(rep));

        CreditApplication app = application();
        CreditApplication.StatusEntry entry = new CreditApplication.StatusEntry();
        entry.setStatus(CreditApplicationStatus.UNDER_VERIFICATION);
        entry.setAt(LocalDateTime.now());
        entry.setByUserId("rep-9");
        entry.setByRole("BRANCH_REP");
        app.setStatusHistory(List.of(entry));

        String actor = service.timelineFor(app).get(0).actor();

        assertTrue(actor.contains("A. Kumar"));
        assertTrue(actor.contains("Branch representative"));
        assertFalse(actor.contains("rep-9"));
    }

    @Test
    void anUnresolvableActorIsDescribedNotExposedAsAnId() {
        CreditApplication app = application();
        CreditApplication.StatusEntry entry = new CreditApplication.StatusEntry();
        entry.setStatus(CreditApplicationStatus.FORWARDED);
        entry.setAt(LocalDateTime.now());
        entry.setByUserId("deleted-account-7");
        entry.setByRole("BRANCH_REP");
        app.setStatusHistory(List.of(entry));

        String actor = service.timelineFor(app).get(0).actor();

        assertFalse(actor.contains("deleted-account-7"));
        assertTrue(actor.startsWith("A staff member"));
    }

    @Test
    void ordersTheWholeTimelineNewestFirstAcrossEverySource() {
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1"))
                .thenReturn(List.of(authorization(LocalDateTime.now().minusDays(5), null)));
        LoanDocument document = new LoanDocument();
        document.setApplicationId("app-1");
        document.setFilename("income.pdf");
        document.setUploadedByUserId("citizen-1");
        document.setUploadedByRole("CITIZEN");
        document.setUploadedAt(LocalDateTime.now().minusDays(1));
        when(documents.findByApplicationIdOrderByUploadedAtDesc("app-1")).thenReturn(List.of(document));

        List<FileAccessService.AccessEvent> timeline = service.timelineFor(application());

        assertEquals("document_uploaded", timeline.get(0).action());
        assertEquals("assist_granted", timeline.get(1).action());
    }

    @Test
    void helpersListMarksWhoStillHasAccess() {
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1")).thenReturn(List.of(
                authorization(LocalDateTime.now().minusDays(1), null),
                authorization(LocalDateTime.now().minusDays(9), LocalDateTime.now().minusDays(8))));

        List<java.util.Map<String, Object>> rows = service.helpersFor("app-1");

        assertEquals(true, rows.get(0).get("active"));
        assertEquals(false, rows.get(1).get("active"));
        assertEquals("CSC operator", rows.get(0).get("typeLabel"));
    }
}

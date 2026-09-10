package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Two things are pinned here.
 *
 * First, the bug WireEnumConvertersTest fixed at its root:
 * ?status=under_verification returned 400 on the real, running app while every
 * CreditApplicationStatus unit test passed. Those tests proved the enum's
 * fromWire() works; they never proved Spring MVC calls it for a query
 * parameter. These exercise the query string a browser actually sends.
 *
 * Second, the scope rule. These tests used to PASS a partnerId in the query
 * string and body and assert it was honoured — which is precisely the hole
 * that was there: the caller named the branch whose files they wanted. The
 * partner now comes from the authenticated rep's own account, so the tests
 * supply a rep and stub the lookup, and one test below asserts that naming
 * someone else's partnerId no longer gets you their queue.
 */
class BranchRepControllerMvcTest {

    private MockMvc mvc;
    private CreditApplicationService service;
    private BranchRepRepository branchReps;

    @BeforeEach
    void setUp() {
        service = mock(CreditApplicationService.class);
        branchReps = mock(BranchRepRepository.class);
        var audit = mock(com.yojnasetu.gateway.repository.AuditLogRepository.class);
        var workflows = mock(com.yojnasetu.gateway.workflow.LoanWorkflowGateway.class);

        when(branchReps.findById("rep-9")).thenReturn(Optional.of(repAt("partner-7", RepType.BANK_BRANCH)));

        BranchRepController controller = new BranchRepController(service, audit, workflows, branchReps);
        mvc = MvcTestSupport.mvc(controller);
    }

    private static BranchRep repAt(String partnerId, RepType type) {
        BranchRep rep = new BranchRep();
        rep.setId("rep-9");
        rep.setRepId("BOB-CP-014");
        rep.setName("A. Kumar");
        rep.setPartnerId(partnerId);
        rep.setRepType(type);
        rep.setActive(true);
        return rep;
    }

    @Test
    void filtersTheQueueBySnakeCaseStatus() throws Exception {
        // The exact query string SIH-CREDIT-API.md documents, and the one that
        // previously came back as a plain 400 with no queue rendered at all.
        when(service.queueForPartner("partner-7", CreditApplicationStatus.UNDER_VERIFICATION))
                .thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications")
                        .principal(MvcTestSupport.rep())
                        .param("status", "under_verification"))
                .andExpect(status().isOk());

        verify(service).queueForPartner("partner-7", CreditApplicationStatus.UNDER_VERIFICATION);
    }

    @Test
    void filtersByAHyphenatedStatusToo() throws Exception {
        when(service.queueForPartner(anyString(), any())).thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications")
                        .principal(MvcTestSupport.rep())
                        .param("status", "missing-docs"))
                .andExpect(status().isOk());

        verify(service).queueForPartner("partner-7", CreditApplicationStatus.MISSING_DOCS);
    }

    @Test
    void rejectsAStatusThatIsNotAStatus() throws Exception {
        mvc.perform(get("/api/v2/branch/applications")
                        .principal(MvcTestSupport.rep())
                        .param("status", "approved"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void listsWithNoStatusFilterAtAll() throws Exception {
        when(service.queueForPartner("partner-7", null)).thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications").principal(MvcTestSupport.rep()))
                .andExpect(status().isOk());

        verify(service).queueForPartner(eq("partner-7"), isNull());
    }

    @Test
    void readsTheQueueFromTheRepsOwnBranchNotTheOneTheyAskedFor() throws Exception {
        // The IDOR: any logged-in rep could read another partner's queue by
        // naming its id. The parameter is now ignored for a rep entirely.
        when(service.queueForPartner(anyString(), any())).thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications")
                        .principal(MvcTestSupport.rep())
                        .param("partnerId", "someone-elses-branch"))
                .andExpect(status().isOk());

        verify(service).queueForPartner(eq("partner-7"), isNull());
        verify(service, never()).queueForPartner(eq("someone-elses-branch"), any());
    }

    @Test
    void refusesAnAccountWithNoBranchAtAll() throws Exception {
        when(branchReps.findById("rep-9")).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/branch/applications").principal(MvcTestSupport.rep()))
                .andExpect(status().isForbidden());
    }

    @Test
    void parsesAReasonCodeAndStatusTogetherInAStatusUpdate() throws Exception {
        CreditApplication app = new CreditApplication();
        app.setId("app-1");
        app.setAssignedPartnerId("partner-7");
        app.setStatus(CreditApplicationStatus.SUBMITTED);
        when(service.findById("app-1")).thenReturn(Optional.of(app));

        CreditApplication rejected = new CreditApplication();
        rejected.setStatus(CreditApplicationStatus.REJECTED);
        when(service.transition(any(), eq(CreditApplicationStatus.REJECTED), anyString(), anyString(),
                eq(ReasonCode.DOCUMENTS_ILLEGIBLE), any(), any())).thenReturn(rejected);

        String body = """
                {"status":"rejected",
                 "reasonCode":"documents_illegible","note":"unreadable scan"}""";

        mvc.perform(post("/api/v2/branch/applications/app-1/status")
                        .principal(MvcTestSupport.rep())
                        .contentType("application/json").content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("rejected"));
    }

    @Test
    void hidesAFileAssignedToAnotherBranchAs404() throws Exception {
        CreditApplication app = new CreditApplication();
        app.setId("app-1");
        app.setAssignedPartnerId("some-other-branch");
        when(service.findById("app-1")).thenReturn(Optional.of(app));

        mvc.perform(post("/api/v2/branch/applications/app-1/status")
                        .principal(MvcTestSupport.rep()).contentType("application/json")
                        .content("""
                                {"status":"under_verification"}"""))
                .andExpect(status().isNotFound());
    }

    @Test
    void refusesACreditDecisionFromAnAssistOnlyHelper() throws Exception {
        // A CSC operator holds an account so they can help assemble a file.
        // Sanctioning or rejecting one is the lender's call, and the block is
        // here rather than in whichever UI happens to render the buttons.
        when(branchReps.findById("rep-9")).thenReturn(Optional.of(repAt(null, RepType.CSC)));

        mvc.perform(post("/api/v2/branch/applications/app-1/status")
                        .principal(MvcTestSupport.rep()).contentType("application/json")
                        .content("""
                                {"status":"sanctioned"}"""))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value(
                        org.hamcrest.Matchers.containsString("cannot record a decision")));

        verify(service, never()).transition(any(), any(), anyString(), anyString(), any(), any(), any());
    }

    @Test
    void listsTheReasonCodeVocabulary() throws Exception {
        mvc.perform(get("/api/v2/branch/applications/reason-codes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].code").exists())
                .andExpect(jsonPath("$[0].description").exists());
    }
}

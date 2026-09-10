package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The regression suite for the bug WireEnumConvertersTest fixed at its root:
 * ?status=under_verification returned 400 on the real, running app while
 * every CreditApplicationStatus unit test passed. Those tests proved the
 * enum's fromWire() method works; they never proved Spring MVC calls it for a
 * query parameter. This file exercises the query string a browser actually
 * sends.
 */
class BranchRepControllerMvcTest {

    private MockMvc mvc;
    private CreditApplicationService service;

    @BeforeEach
    void setUp() {
        service = mock(CreditApplicationService.class);
        var audit = mock(com.yojnasetu.gateway.repository.AuditLogRepository.class);
        var workflows = mock(com.yojnasetu.gateway.workflow.LoanWorkflowGateway.class);
        BranchRepController controller = new BranchRepController(service, audit, workflows);
        mvc = MvcTestSupport.mvc(controller);
    }

    @Test
    void filtersTheQueueBySnakeCaseStatus() throws Exception {
        // The exact query string SIH-CREDIT-API.md documents, and the one that
        // previously came back as a plain 400 with no queue rendered at all.
        when(service.queueForPartner("partner-7", CreditApplicationStatus.UNDER_VERIFICATION))
                .thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications")
                        .param("partnerId", "partner-7")
                        .param("status", "under_verification"))
                .andExpect(status().isOk());

        verify(service).queueForPartner("partner-7", CreditApplicationStatus.UNDER_VERIFICATION);
    }

    @Test
    void filtersByAHyphenatedStatusToo() throws Exception {
        when(service.queueForPartner(anyString(), any())).thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications")
                        .param("partnerId", "partner-7")
                        .param("status", "missing-docs"))
                .andExpect(status().isOk());

        verify(service).queueForPartner("partner-7", CreditApplicationStatus.MISSING_DOCS);
    }

    @Test
    void rejectsAStatusThatIsNotAStatus() throws Exception {
        mvc.perform(get("/api/v2/branch/applications")
                        .param("partnerId", "partner-7")
                        .param("status", "approved"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void listsWithNoStatusFilterAtAll() throws Exception {
        when(service.queueForPartner("partner-7", null)).thenReturn(List.of());

        mvc.perform(get("/api/v2/branch/applications").param("partnerId", "partner-7"))
                .andExpect(status().isOk());

        verify(service).queueForPartner(eq("partner-7"), isNull());
    }

    @Test
    void requiresAPartnerId() throws Exception {
        mvc.perform(get("/api/v2/branch/applications")).andExpect(status().isBadRequest());
    }

    @Test
    void parsesAReasonCodeAndStatusTogetherInAStatusUpdate() throws Exception {
        CreditApplication app = new CreditApplication();
        app.setId("app-1");
        app.setAssignedPartnerId("partner-7");
        app.setStatus(CreditApplicationStatus.SUBMITTED);
        when(service.findById("app-1")).thenReturn(java.util.Optional.of(app));

        CreditApplication rejected = new CreditApplication();
        rejected.setStatus(CreditApplicationStatus.REJECTED);
        when(service.transition(any(), eq(CreditApplicationStatus.REJECTED), anyString(), anyString(),
                eq(ReasonCode.DOCUMENTS_ILLEGIBLE), any(), any())).thenReturn(rejected);

        String body = """
                {"partnerId":"partner-7","status":"rejected",
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
        when(service.findById("app-1")).thenReturn(java.util.Optional.of(app));

        mvc.perform(post("/api/v2/branch/applications/app-1/status")
                        .principal(MvcTestSupport.rep()).contentType("application/json")
                        .content("""
                                {"partnerId":"partner-7","status":"under_verification"}"""))
                .andExpect(status().isNotFound());
    }

    @Test
    void listsTheReasonCodeVocabulary() throws Exception {
        mvc.perform(get("/api/v2/branch/applications/reason-codes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].code").exists())
                .andExpect(jsonPath("$[0].description").exists());
    }
}

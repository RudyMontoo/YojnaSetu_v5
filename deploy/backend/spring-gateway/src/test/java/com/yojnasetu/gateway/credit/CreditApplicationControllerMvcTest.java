package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import static com.yojnasetu.gateway.credit.MvcTestSupport.citizen;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * CreditApplicationController through real MVC binding, with
 * CreditApplicationService and ConsentService mocked — the state machine and
 * consent logic already have their own suites. What is under test here is the
 * wiring: does the right status code come back for each failure mode, and does
 * consent actually get checked before submit ever reaches the service.
 */
class CreditApplicationControllerMvcTest {

    private MockMvc mvc;
    private CreditApplicationService service;
    private ConsentService consents;

    @BeforeEach
    void setUp() {
        service = mock(CreditApplicationService.class);
        consents = mock(ConsentService.class);
        var workflows = mock(com.yojnasetu.gateway.workflow.LoanWorkflowGateway.class);
        var audit = mock(com.yojnasetu.gateway.repository.AuditLogRepository.class);

        CreditApplicationController controller =
                new CreditApplicationController(service, workflows, consents, audit);
        mvc = MvcTestSupport.mvc(controller);
    }

    private static CreditApplication application(CreditApplicationStatus status) {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        a.setStatus(status);
        return a;
    }

    @Test
    void refusesSubmitWithoutConsentBeforeTouchingTheStateMachine() throws Exception {
        when(service.getForCitizen("citizen-1", "app-1")).thenReturn(application(CreditApplicationStatus.DRAFT));
        doThrow(new CreditApplicationService.TransitionException(
                CreditApplicationService.Failure.FORBIDDEN, "Your consent is needed first: ..."))
                .when(consents).requireConsent("citizen-1", ConsentPurpose.PARTNER_SHARING, "app-1");

        mvc.perform(post("/api/v2/sih/applications/app-1/submit").principal(citizen()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("consent")));

        // The whole point: the transition must never be attempted.
        verify(service, org.mockito.Mockito.never())
                .transition(any(), any(), anyString(), anyString(), any(), any(), any());
    }

    @Test
    void submitsOnceConsentIsInPlace() throws Exception {
        CreditApplication draft = application(CreditApplicationStatus.DRAFT);
        CreditApplication submitted = application(CreditApplicationStatus.SUBMITTED);
        when(service.getForCitizen("citizen-1", "app-1")).thenReturn(draft);
        when(service.transition(any(), any(), anyString(), anyString(), any(), any(), any()))
                .thenReturn(submitted);

        mvc.perform(post("/api/v2/sih/applications/app-1/submit").principal(citizen()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("submitted"));
    }

    @Test
    void mapsNotFoundToA404() throws Exception {
        when(service.getForCitizen("citizen-1", "app-1")).thenThrow(
                new CreditApplicationService.TransitionException(
                        CreditApplicationService.Failure.NOT_FOUND, "Application not found"));

        mvc.perform(post("/api/v2/sih/applications/app-1/submit").principal(citizen()))
                .andExpect(status().isNotFound());
    }

    @Test
    void mapsAnIllegalTransitionToA409() throws Exception {
        when(service.getForCitizen("citizen-1", "app-1"))
                .thenReturn(application(CreditApplicationStatus.DISBURSED));
        when(service.transition(any(), any(), anyString(), anyString(), any(), any(), any()))
                .thenThrow(new CreditApplicationService.TransitionException(
                        CreditApplicationService.Failure.CONFLICT, "This application is closed"));

        mvc.perform(post("/api/v2/sih/applications/app-1/submit").principal(citizen()))
                .andExpect(status().isConflict());
    }

    @Test
    void createParsesAFullApplicationBodyIncludingEnums() throws Exception {
        when(service.create(anyString(), any())).thenReturn(application(CreditApplicationStatus.DRAFT));
        // The body names a partner, so the controller also calls
        // assignPartner — an unstubbed mock returns null there, which is a
        // realistic-looking but misleading failure if left unstubbed.
        when(service.assignPartner(any(), anyString(), any(), any()))
                .thenReturn(application(CreditApplicationStatus.DRAFT));

        String body = """
                {"productId":"micro-finance","estimatedCost":100000,"annualIncome":300000,
                 "category":"sc","tenureMonths":36,"moratoriumMode":"capitalise",
                 "verificationMode":"manual","partnerId":"p-7","partnerName":"BoB CP",
                 "partnerType":"PSB"}""";

        mvc.perform(post("/api/v2/sih/applications")
                        .principal(citizen()).contentType("application/json").content(body))
                .andExpect(status().isCreated());
    }

    @Test
    void refusesAPartnerThatCannotDeliverTheScheme() throws Exception {
        when(service.create(anyString(), any())).thenReturn(application(CreditApplicationStatus.DRAFT));
        when(service.assignPartner(any(), anyString(), any(), any()))
                .thenThrow(new CreditApplicationService.TransitionException(
                        CreditApplicationService.Failure.BAD_REQUEST,
                        "Micro Finance Scheme (MFS) is not offered by a Micro-finance institution"));

        String body = """
                {"productId":"micro-finance","estimatedCost":100000,"partnerId":"mfi-1",
                 "partnerType":"NBFC-MFI"}""";

        mvc.perform(post("/api/v2/sih/applications")
                        .principal(citizen()).contentType("application/json").content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value(org.hamcrest.Matchers.containsString("not offered by")));
    }
}

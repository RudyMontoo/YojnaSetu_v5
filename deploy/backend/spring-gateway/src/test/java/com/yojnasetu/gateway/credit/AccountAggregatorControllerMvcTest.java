package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AccountAggregatorControllerMvcTest {

    private MockMvc mvc;
    private AccountAggregatorService service;
    private CreditApplicationService applications;

    @BeforeEach
    void setUp() {
        service = mock(AccountAggregatorService.class);
        applications = mock(CreditApplicationService.class);
        mvc = MvcTestSupport.mvc(new AccountAggregatorController(service, applications));
    }

    @Test
    void refusesAConsentRequestForAnApplicationThatIsNotTheCallers() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-other"))
                .thenThrow(new TransitionException(Failure.NOT_FOUND, "Application not found"));

        mvc.perform(post("/api/v2/sih/account-aggregator/consent-request")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("{\"applicationId\":\"app-other\",\"vua\":\"9999999999@onemoney\"}"))
                .andExpect(status().isNotFound());

        verify(service, never()).createConsentRequest(anyString(), anyString(), anyString());
    }

    @Test
    void createsAConsentRequestForTheCallersOwnApplication() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-1")).thenReturn(new CreditApplication());
        AaConsentRequest request = new AaConsentRequest();
        request.setConsentHandle("handle-1");
        request.setStatus("pending");
        when(service.createConsentRequest("citizen-1", "app-1", "9999999999@onemoney")).thenReturn(request);

        mvc.perform(post("/api/v2/sih/account-aggregator/consent-request")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("{\"applicationId\":\"app-1\",\"vua\":\"9999999999@onemoney\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.consentHandle").value("handle-1"));
    }

    @Test
    void reportsNoConsentRequestWhenNoneExistsYet() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-1")).thenReturn(new CreditApplication());
        when(service.latestFor("app-1")).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/sih/account-aggregator/consent-status")
                        .principal(MvcTestSupport.citizen())
                        .param("applicationId", "app-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("none"));
    }

    @Test
    void refusesConsentStatusForAnApplicationThatIsNotTheCallers() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-other"))
                .thenThrow(new TransitionException(Failure.NOT_FOUND, "Application not found"));

        mvc.perform(get("/api/v2/sih/account-aggregator/consent-status")
                        .principal(MvcTestSupport.citizen())
                        .param("applicationId", "app-other"))
                .andExpect(status().isNotFound());

        verify(service, never()).latestFor(anyString());
    }
}

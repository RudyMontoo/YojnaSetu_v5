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

/**
 * The one thing worth pinning at the HTTP layer here: a citizen cannot start
 * a DigiLocker link, or read link status/documents, against an application
 * that isn't theirs — see DigiLockerController's ownership-check comment.
 */
class DigiLockerControllerMvcTest {

    private MockMvc mvc;
    private DigiLockerService service;
    private CreditApplicationService applications;

    @BeforeEach
    void setUp() {
        service = mock(DigiLockerService.class);
        applications = mock(CreditApplicationService.class);
        mvc = MvcTestSupport.mvc(new DigiLockerController(service, applications));
    }

    @Test
    void refusesToStartALinkForAnApplicationThatIsNotTheCallers() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-other"))
                .thenThrow(new TransitionException(Failure.NOT_FOUND, "Application not found"));

        mvc.perform(post("/api/v2/sih/digilocker/authorize-url")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("{\"applicationId\":\"app-other\"}"))
                .andExpect(status().isNotFound());

        verify(service, never()).startLink(anyString(), anyString());
    }

    @Test
    void startsALinkForTheCallersOwnApplication() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-1")).thenReturn(new CreditApplication());
        when(service.startLink("citizen-1", "app-1"))
                .thenReturn(new DigiLockerService.AuthorizeUrl("https://digilocker.example/authorize?state=s-1", "s-1"));

        mvc.perform(post("/api/v2/sih/digilocker/authorize-url")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("{\"applicationId\":\"app-1\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.state").value("s-1"));
    }

    @Test
    void refusesToReadStatusForAnApplicationThatIsNotTheCallers() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-other"))
                .thenThrow(new TransitionException(Failure.NOT_FOUND, "Application not found"));

        mvc.perform(get("/api/v2/sih/digilocker/status")
                        .principal(MvcTestSupport.citizen())
                        .param("applicationId", "app-other"))
                .andExpect(status().isNotFound());

        verify(service, never()).linkedFor(anyString());
    }

    @Test
    void reportsUnlinkedWhenNoLinkExists() throws Exception {
        when(applications.getForCitizen("citizen-1", "app-1")).thenReturn(new CreditApplication());
        when(service.linkedFor("app-1")).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/sih/digilocker/status")
                        .principal(MvcTestSupport.citizen())
                        .param("applicationId", "app-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.linked").value(false));
    }

    @Test
    void callbackNeedsNoCitizenAuthenticationButStillRunsTheStateGuard() throws Exception {
        when(service.completeLink("bad-state", "code")).thenThrow(
                new TransitionException(Failure.NOT_FOUND, "Unknown or expired link attempt"));

        mvc.perform(get("/api/v2/sih/digilocker/callback")
                        .param("state", "bad-state")
                        .param("code", "code"))
                .andExpect(status().isNotFound());
    }
}

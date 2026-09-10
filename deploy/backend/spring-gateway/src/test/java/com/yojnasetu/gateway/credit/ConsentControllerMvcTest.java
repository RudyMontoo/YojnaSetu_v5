package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The other half of the enum-in-a-path-variable bug: DELETE
 * /consents/{purpose} took the exact same wrong turn as the branch queue's
 * status filter, for the exact same reason.
 */
class ConsentControllerMvcTest {

    private MockMvc mvc;
    private ConsentService consents;

    @BeforeEach
    void setUp() {
        consents = mock(ConsentService.class);
        var audit = mock(com.yojnasetu.gateway.repository.AuditLogRepository.class);
        mvc = MvcTestSupport.mvc(new ConsentController(consents, audit));
    }

    @Test
    void revokesAPurposeGivenAsASnakeCasePathVariable() throws Exception {
        when(consents.revoke("citizen-1", ConsentPurpose.PARTNER_SHARING, null)).thenReturn(1);

        mvc.perform(delete("/api/v2/sih/consents/partner_sharing").principal(MvcTestSupport.citizen()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.revoked").value(1))
                .andExpect(jsonPath("$.purpose").value("partner_sharing"));

        verify(consents).revoke("citizen-1", ConsentPurpose.PARTNER_SHARING, null);
    }

    @Test
    void scopesRevocationToOneApplicationViaAQueryParameter() throws Exception {
        when(consents.revoke(anyString(), any(), anyString())).thenReturn(1);

        mvc.perform(delete("/api/v2/sih/consents/partner_sharing")
                        .principal(MvcTestSupport.citizen())
                        .param("applicationId", "app-1"))
                .andExpect(status().isOk());

        verify(consents).revoke("citizen-1", ConsentPurpose.PARTNER_SHARING, "app-1");
    }

    @Test
    void rejectsAPurposeThatIsNotOnTheList() throws Exception {
        mvc.perform(delete("/api/v2/sih/consents/everything").principal(MvcTestSupport.citizen()))
                .andExpect(status().isBadRequest());
    }

    @Test
    void neverErrorsWhenThereWasNothingToWithdraw() throws Exception {
        when(consents.revoke(anyString(), any(), isNull())).thenReturn(0);

        mvc.perform(delete("/api/v2/sih/consents/document_verification")
                        .principal(MvcTestSupport.citizen()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.revoked").value(0));
    }

    @Test
    void servesTheExactStatementsAPurposeShowsACitizen() throws Exception {
        mvc.perform(get("/api/v2/sih/consents/purposes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].statement").value(org.hamcrest.Matchers.startsWith("I agree")));
    }
}

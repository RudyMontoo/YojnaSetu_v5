package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Base64;
import java.util.List;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The HTTP-layer half of the self-onboarding flow: admin gating on the
 * review endpoints and citizen-scoping on the application endpoints, per
 * BranchRepApplicationController's own in-handler ROLE_ADMIN check rather
 * than a path matcher.
 */
class BranchRepApplicationControllerMvcTest {

    private static final FieldEncryptionService CIPHER = new FieldEncryptionService(
            Base64.getEncoder().encodeToString(new byte[32]));

    private MockMvc mvc;
    private BranchRepApplicationService service;

    @BeforeEach
    void setUp() {
        service = mock(BranchRepApplicationService.class);
        mvc = MvcTestSupport.mvc(new BranchRepApplicationController(service, CIPHER));
    }

    @Test
    void aCitizenCanSubmitAnApplication() throws Exception {
        BranchRepApplication saved = new BranchRepApplication();
        saved.setStatus("pending");
        saved.setAadhaarVerified(true);
        when(service.apply(anyString(), any())).thenReturn(saved);

        mvc.perform(post("/api/v2/sih/branch-rep-applications")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("""
                                {"fullName":"Sita Devi","phone":"9876543210","aadhaar":"234123412346",
                                 "pan":"ABCDE1234F","repType":"csc","organisation":"CSC-UP-0142"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("pending"))
                .andExpect(jsonPath("$.aadhaarVerified").value(true));
    }

    @Test
    void surfacesAValidationFailureAsBadRequest() throws Exception {
        when(service.apply(anyString(), any())).thenThrow(
                new TransitionException(Failure.BAD_REQUEST, "PAN must look like ABCDE1234F"));

        mvc.perform(post("/api/v2/sih/branch-rep-applications")
                        .principal(MvcTestSupport.citizen())
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void aCitizenWithNoApplicationSeesNone() throws Exception {
        when(service.myApplication("citizen-1")).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/sih/branch-rep-applications/mine").principal(MvcTestSupport.citizen()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("none"));
    }

    @Test
    void aNonAdminCannotListPendingApplications() throws Exception {
        mvc.perform(get("/api/v2/sih/branch-rep-applications/pending").principal(MvcTestSupport.citizen()))
                .andExpect(status().isForbidden());
    }

    @Test
    void anAdminCanListPendingApplications() throws Exception {
        when(service.pending()).thenReturn(List.of());

        mvc.perform(get("/api/v2/sih/branch-rep-applications/pending").principal(MvcTestSupport.admin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.applications").isArray());
    }

    @Test
    void aNonAdminCannotApprove() throws Exception {
        mvc.perform(post("/api/v2/sih/branch-rep-applications/app-1/approve").principal(MvcTestSupport.citizen()))
                .andExpect(status().isForbidden());
    }

    @Test
    void anAdminApprovalReturnsTheMintedCredentials() throws Exception {
        when(service.approve("app-1", "admin-1"))
                .thenReturn(new BranchRepApplicationService.ApprovalResult("CSC-AB12CD", "tmp-pass", "sita@example.com"));

        mvc.perform(post("/api/v2/sih/branch-rep-applications/app-1/approve").principal(MvcTestSupport.admin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.repId").value("CSC-AB12CD"))
                .andExpect(jsonPath("$.tempPassword").value("tmp-pass"))
                .andExpect(jsonPath("$.emailedTo").value("sita@example.com"));
    }

    @Test
    void aNonAdminCannotReject() throws Exception {
        mvc.perform(post("/api/v2/sih/branch-rep-applications/app-1/reject").principal(MvcTestSupport.citizen()))
                .andExpect(status().isForbidden());
    }

    @Test
    void anAdminRejectionSucceeds() throws Exception {
        mvc.perform(post("/api/v2/sih/branch-rep-applications/app-1/reject").principal(MvcTestSupport.admin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("rejected"));
    }
}

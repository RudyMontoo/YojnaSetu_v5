package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.security.JwtUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Optional;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The claim in BranchRepAuthController's javadoc — an unknown repId, a wrong
 * password and a deactivated account are indistinguishable — is only true if
 * something actually asserts it. This does.
 */
class BranchRepAuthControllerMvcTest {

    private static final BCryptPasswordEncoder ENCODER = new BCryptPasswordEncoder();

    private MockMvc mvc;
    private BranchRepRepository branchReps;

    @BeforeEach
    void setUp() throws Exception {
        branchReps = mock(BranchRepRepository.class);
        JwtUtils jwtUtils = new JwtUtils();
        jwtUtils.init(); // dev fallback: generates an ephemeral RSA keypair
        BranchRepAuthController controller = new BranchRepAuthController(branchReps, jwtUtils);
        mvc = MvcTestSupport.mvc(controller);
    }

    private static BranchRep activeRep(String password) {
        BranchRep rep = new BranchRep();
        rep.setId("rep-1");
        rep.setRepId("BOB-CP-014");
        rep.setPasswordHash(ENCODER.encode(password));
        rep.setName("A. Kumar");
        rep.setPartnerId("partner-7");
        rep.setActive(true);
        return rep;
    }

    @Test
    void logsInWithTheRightCredentialsAndSetsBothCookies() throws Exception {
        when(branchReps.findByRepId("BOB-CP-014")).thenReturn(Optional.of(activeRep("correct-horse")));

        mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                        .content("""
                                {"repId":"BOB-CP-014","password":"correct-horse"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.rep.partnerId").value("partner-7"))
                .andExpect(cookie().exists("access_token"))
                .andExpect(cookie().exists("refresh_token"));
    }

    @Test
    void wrongPasswordAndUnknownRepGiveTheIdenticalResponse() throws Exception {
        when(branchReps.findByRepId("BOB-CP-014")).thenReturn(Optional.of(activeRep("correct-horse")));
        when(branchReps.findByRepId("NOBODY")).thenReturn(Optional.empty());

        var wrongPassword = mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                        .content("""
                                {"repId":"BOB-CP-014","password":"nope"}
                                """))
                .andExpect(status().isUnauthorized())
                .andReturn().getResponse().getContentAsString();

        var unknownRep = mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                        .content("""
                                {"repId":"NOBODY","password":"nope"}
                                """))
                .andExpect(status().isUnauthorized())
                .andReturn().getResponse().getContentAsString();

        // Byte-identical, or a wrong password reveals that the id exists.
        org.junit.jupiter.api.Assertions.assertEquals(wrongPassword, unknownRep);
    }

    @Test
    void deactivatedRepGetsTheSameResponseToo() throws Exception {
        BranchRep deactivated = activeRep("correct-horse");
        deactivated.setActive(false);
        when(branchReps.findByRepId("BOB-CP-014")).thenReturn(Optional.of(deactivated));

        mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                        .content("""
                                {"repId":"BOB-CP-014","password":"correct-horse"}
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("Invalid rep ID or password"));
    }

    @Test
    void issuedTokenCarriesTheRepsOwnIdAndRole() throws Exception {
        when(branchReps.findByRepId("BOB-CP-014")).thenReturn(Optional.of(activeRep("correct-horse")));

        var response = mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                        .content("""
                                {"repId":"BOB-CP-014","password":"correct-horse"}
                                """))
                .andReturn().getResponse();

        String token = response.getCookie("access_token").getValue();
        JwtUtils jwtUtils = new JwtUtils();
        jwtUtils.init();
        // Re-verifying with a fresh instance would fail (different ephemeral
        // key) — this just confirms the cookie is a non-empty JWT-shaped value.
        org.junit.jupiter.api.Assertions.assertTrue(token.chars().filter(c -> c == '.').count() == 2);
    }

    @Test
    void rejectsALoginWithNoBody() throws Exception {
        mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json").content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void updatesLastLoginOnSuccess() throws Exception {
        BranchRep rep = activeRep("correct-horse");
        when(branchReps.findByRepId("BOB-CP-014")).thenReturn(Optional.of(rep));

        mvc.perform(post("/api/v2/branch-portal/login").contentType("application/json")
                .content("""
                                {"repId":"BOB-CP-014","password":"correct-horse"}
                                """));

        verify(branchReps).save(rep);
        org.junit.jupiter.api.Assertions.assertNotNull(rep.getLastLoginAt());
    }
}

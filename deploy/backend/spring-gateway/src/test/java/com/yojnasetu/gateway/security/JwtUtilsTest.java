package com.yojnasetu.gateway.security;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * RS256 JWT issuing/verification (CLAUDE.md security rule #5). Runs against
 * an ephemeral in-memory keypair — no key files, no Spring context, no Mongo.
 * This is the Java mirror of ai_service's test_jwt_auth.py: the two services
 * must agree on the token contract (RS256, `type` claim, subject = userId).
 */
class JwtUtilsTest {

    private JwtUtils jwt;

    @BeforeEach
    void setUp() throws Exception {
        jwt = new JwtUtils();
        // No key paths → init() generates an ephemeral RSA keypair (its
        // documented dev fallback), which is exactly what we want in a test.
        ReflectionTestUtils.setField(jwt, "privateKeyPath", "");
        ReflectionTestUtils.setField(jwt, "publicKeyPath", "");
        ReflectionTestUtils.setField(jwt, "accessTokenExpiryMinutes", 60L);
        ReflectionTestUtils.setField(jwt, "refreshTokenExpiryDays", 7L);
        jwt.init();
    }

    @Test
    void accessTokenCarriesSubjectRoleAndType() {
        String token = jwt.generateAccessToken("user-123", "CITIZEN");
        Claims claims = jwt.parseClaims(token);
        assertThat(claims.getSubject()).isEqualTo("user-123");
        assertThat(claims.get("role")).isEqualTo("CITIZEN");
        assertThat(claims.get("type")).isEqualTo("access");
    }

    @Test
    void validateAccessTokenReturnsUserId() {
        String token = jwt.generateAccessToken("user-123", "CITIZEN");
        assertThat(jwt.validateAndGetUserId(token, "access")).isEqualTo("user-123");
    }

    @Test
    void accessTokenRejectedWhenRefreshExpected() {
        String access = jwt.generateAccessToken("user-123", "CITIZEN");
        assertThat(jwt.validateAndGetUserId(access, "refresh")).isNull();
    }

    @Test
    void refreshTokenRejectedWhenAccessExpected() {
        String refresh = jwt.generateRefreshToken("user-123");
        assertThat(jwt.validateAndGetUserId(refresh, "access")).isNull();
        // but is valid as a refresh token
        assertThat(jwt.validateAndGetUserId(refresh, "refresh")).isEqualTo("user-123");
    }

    @Test
    void garbageTokenReturnsNullNeverThrows() {
        assertThat(jwt.validateAndGetUserId("not.a.jwt", "access")).isNull();
        assertThat(jwt.validateAndGetUserId("", "access")).isNull();
    }

    @Test
    void tokenSignedByADifferentKeypairIsRejected() throws Exception {
        String token = jwt.generateAccessToken("user-123", "CITIZEN");

        JwtUtils attacker = new JwtUtils();
        ReflectionTestUtils.setField(attacker, "privateKeyPath", "");
        ReflectionTestUtils.setField(attacker, "publicKeyPath", "");
        ReflectionTestUtils.setField(attacker, "accessTokenExpiryMinutes", 60L);
        ReflectionTestUtils.setField(attacker, "refreshTokenExpiryDays", 7L);
        attacker.init(); // a DIFFERENT ephemeral keypair

        // A token from `jwt` must not verify against `attacker`'s public key.
        assertThat(attacker.validateAndGetUserId(token, "access")).isNull();
    }

    @Test
    void expirySecondsMatchConfiguredValues() {
        assertThat(jwt.getAccessTokenExpirySeconds()).isEqualTo(60 * 60);
        assertThat(jwt.getRefreshTokenExpirySeconds()).isEqualTo(7 * 86_400);
    }
}

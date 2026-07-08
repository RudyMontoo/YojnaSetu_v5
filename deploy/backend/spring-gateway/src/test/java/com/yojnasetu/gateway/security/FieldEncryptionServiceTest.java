package com.yojnasetu.gateway.security;

import org.junit.jupiter.api.Test;

import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * AES-256-GCM field encryption (CLAUDE.md security rule #4: PII encrypted
 * before every Mongo write). Pure service — no Spring context, no Mongo.
 * A regression here would silently store citizen name/dob/phone in the clear.
 */
class FieldEncryptionServiceTest {

    // 32 bytes → valid AES-256 key. A fixed test key (not a real secret).
    private static final String KEY_32 = Base64.getEncoder().encodeToString(new byte[32]);

    private final FieldEncryptionService svc = new FieldEncryptionService(KEY_32);

    @Test
    void encryptThenDecryptRoundTrips() {
        String plain = "Rajesh Kumar Sharma";
        assertThat(svc.decrypt(svc.encrypt(plain))).isEqualTo(plain);
    }

    @Test
    void ciphertextIsNotThePlaintext() {
        String cipher = svc.encrypt("9876543210");
        assertThat(cipher).doesNotContain("9876543210");
    }

    @Test
    void sameInputProducesDifferentCiphertextButBothDecrypt() {
        // Random IV per call → identical plaintext must not yield identical
        // ciphertext (otherwise equal values leak through equality).
        String a = svc.encrypt("same value");
        String b = svc.encrypt("same value");
        assertThat(a).isNotEqualTo(b);
        assertThat(svc.decrypt(a)).isEqualTo("same value");
        assertThat(svc.decrypt(b)).isEqualTo("same value");
    }

    @Test
    void nullPassesThroughBothWays() {
        assertThat(svc.encrypt(null)).isNull();
        assertThat(svc.decrypt(null)).isNull();
    }

    @Test
    void unicodeSurvivesRoundTrip() {
        String hindi = "राजेश कुमार";
        assertThat(svc.decrypt(svc.encrypt(hindi))).isEqualTo(hindi);
    }

    @Test
    void tamperedCiphertextFailsToDecrypt() {
        // GCM is authenticated — flipping a byte must be rejected, not
        // silently return garbage.
        String cipher = svc.encrypt("sensitive");
        byte[] raw = Base64.getDecoder().decode(cipher);
        raw[raw.length - 1] ^= 0x01;
        String tampered = Base64.getEncoder().encodeToString(raw);
        assertThatThrownBy(() -> svc.decrypt(tampered))
                .isInstanceOf(RuntimeException.class);
    }

    @Test
    void sha256HashIsDeterministicAndSaltSensitive() {
        String h1 = svc.sha256Hash("123412341234", "salt-A");
        String h2 = svc.sha256Hash("123412341234", "salt-A");
        String h3 = svc.sha256Hash("123412341234", "salt-B");
        assertThat(h1).isEqualTo(h2);       // deterministic
        assertThat(h1).isNotEqualTo(h3);    // salt changes the digest
        assertThat(h1).doesNotContain("123412341234"); // never the raw UID
    }

    @Test
    void wrongKeyLengthRejectedAtConstruction() {
        String shortKey = Base64.getEncoder().encodeToString(new byte[16]); // AES-128 sized
        assertThatThrownBy(() -> new FieldEncryptionService(shortKey))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("32 bytes");
    }
}

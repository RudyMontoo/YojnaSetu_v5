package com.yojnasetu.gateway.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

/**
 * AES-256-GCM field-level encryption, per CLAUDE.md's L1 security layer and
 * docs/PRANJAL_HANDOFF.md's spec. Used by CitizenProfileService — never
 * called directly from a controller.
 *
 * encryption.key must be a 32-byte key, base64-encoded, from
 * FIELD_ENCRYPTION_KEY (GCP Secret Manager in prod). Generate one with:
 *     openssl rand -base64 32
 */
@Service
public class FieldEncryptionService {

    private final SecretKey aesKey;

    public FieldEncryptionService(@Value("${encryption.key}") String base64Key) {
        byte[] keyBytes = Base64.getDecoder().decode(base64Key);
        if (keyBytes.length != 32) {
            throw new IllegalArgumentException(
                    "encryption.key must decode to exactly 32 bytes (AES-256) — got " + keyBytes.length
                            + ". Generate one with: openssl rand -base64 32");
        }
        this.aesKey = new SecretKeySpec(keyBytes, "AES");
    }

    public String encrypt(String plaintext) {
        if (plaintext == null) return null;
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            byte[] iv = new byte[12];
            new SecureRandom().nextBytes(iv);
            cipher.init(Cipher.ENCRYPT_MODE, aesKey, new GCMParameterSpec(128, iv));
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new RuntimeException("Encryption failed", e);
        }
    }

    public String decrypt(String ciphertext) {
        if (ciphertext == null) return null;
        try {
            byte[] combined = Base64.getDecoder().decode(ciphertext);
            byte[] iv = Arrays.copyOfRange(combined, 0, 12);
            byte[] encrypted = Arrays.copyOfRange(combined, 12, combined.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, aesKey, new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new RuntimeException("Decryption failed", e);
        }
    }

    /** Aadhaar / PPO number: one-way hash only — never decrypt, never store the raw UID. */
    public String sha256Hash(String rawValue, String salt) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return Base64.getEncoder().encodeToString(
                    digest.digest((rawValue + salt).getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new RuntimeException("Hashing failed", e);
        }
    }
}

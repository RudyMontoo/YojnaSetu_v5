package com.yojnasetu.gateway.service;

import com.yojnasetu.gateway.model.CitizenProfile;
import com.yojnasetu.gateway.repository.CitizenProfileRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Optional;

/**
 * Owns PII encryption for citizen_profiles — per PRANJAL_HANDOFF.md: "Use
 * this service in CitizenProfileService, never in the controller directly."
 * Every read decrypts, every write encrypts; callers never see ciphertext.
 */
@Service
public class CitizenProfileService {

    private final CitizenProfileRepository repository;
    private final FieldEncryptionService encryption;

    @Value("${encryption.aadhaar-salt}")
    private String aadhaarSalt;

    private static final java.util.List<String> COMPLETENESS_FIELDS = java.util.List.of(
            "annualIncome", "category", "occupation", "isBpl", "state", "district", "familySize");

    public CitizenProfileService(CitizenProfileRepository repository, FieldEncryptionService encryption) {
        this.repository = repository;
        this.encryption = encryption;
    }

    public Optional<CitizenProfile> findDecrypted(String userId) {
        return repository.findByUserId(userId).map(this::decrypt);
    }

    /** `profile` must already be plaintext (as built by the controller from a decrypted
     * read merged with request updates) — this method encrypts it for storage and
     * returns the saved result decrypted back to plaintext for the caller to serialize. */
    public CitizenProfile saveEncrypted(CitizenProfile profile) {
        recalcCompleteness(profile);
        profile.setUpdatedAt(LocalDateTime.now());
        String plainName = profile.getName();
        String plainDob = profile.getDob();
        String plainPhone = profile.getPhone();

        CitizenProfile saved = repository.save(encrypt(profile));

        saved.setName(plainName);
        saved.setDob(plainDob);
        saved.setPhone(plainPhone);
        return saved;
    }

    public String hashAadhaar(String rawAadhaar) {
        return encryption.sha256Hash(rawAadhaar, aadhaarSalt);
    }

    public String hashPpo(String rawPpo) {
        return encryption.sha256Hash(rawPpo, aadhaarSalt); // same salt scheme, different field per ADR context
    }

    private void recalcCompleteness(CitizenProfile p) {
        long filled = 0;
        if (p.getAnnualIncome() != null) filled++;
        if (p.getCategory() != null) filled++;
        if (p.getOccupation() != null) filled++;
        if (p.getIsBpl() != null) filled++;
        if (p.getState() != null) filled++;
        if (p.getDistrict() != null) filled++;
        if (p.getFamilySize() != null) filled++;
        p.setProfileCompleteness((int) ((filled * 100) / COMPLETENESS_FIELDS.size()));
    }

    private CitizenProfile encrypt(CitizenProfile p) {
        p.setName(encryption.encrypt(p.getName()));
        p.setDob(encryption.encrypt(p.getDob()));
        p.setPhone(encryption.encrypt(p.getPhone()));
        return p;
    }

    private CitizenProfile decrypt(CitizenProfile p) {
        // Defensive: if a field somehow isn't ciphertext (e.g. legacy/malformed data), don't blow up the whole read
        try { p.setName(encryption.decrypt(p.getName())); } catch (Exception ignored) {}
        try { p.setDob(encryption.decrypt(p.getDob())); } catch (Exception ignored) {}
        try { p.setPhone(encryption.decrypt(p.getPhone())); } catch (Exception ignored) {}
        return p;
    }
}

package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.AadhaarOfflineEkycExtractor.ExtractedKyc;
import com.yojnasetu.gateway.credit.AadhaarOfflineEkycExtractor.ExtractionException;
import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.FileInputStream;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Spring-side wiring around {@link AadhaarOfflineEkycExtractor}: loads the
 * trusted UIDAI certificate (if one is configured), stores what the extractor
 * finds, and enforces the same document-count/lifecycle rules
 * {@code LoanDocumentService} already enforces for scans.
 *
 * No UIDAI production certificate is configured anywhere in this deployment
 * as of this writing — {@link #trustedCert} is null, so every record this
 * writes has {@code signatureVerified=false}. That is the honest state, not a
 * bug: the parsing, masking, and encryption all work today; cryptographic
 * proof that a given file was genuinely issued by UIDAI is the one piece
 * that needs a real certificate to switch on, exactly like
 * {@code VerificationMode.DIGILOCKER.isAvailable()} being false for the same
 * kind of reason.
 */
@Service
public class AadhaarOfflineEkycService {

    private static final Logger LOG = LoggerFactory.getLogger(AadhaarOfflineEkycService.class);

    /** Mirrors LoanDocumentService's own limit — same "phone-photo-of-a-document" scale. */
    private static final int MAX_ZIP_BYTES = 8 * 1024 * 1024;

    private final AadhaarEkycRepository records;
    private final FieldEncryptionService encryption;
    private final X509Certificate trustedCert;

    public AadhaarOfflineEkycService(AadhaarEkycRepository records,
                                     FieldEncryptionService encryption,
                                     @Value("${app.aadhaar.uidai-cert-path:}") String certPath) {
        this.records = records;
        this.encryption = encryption;
        this.trustedCert = loadCert(certPath);
    }

    private static X509Certificate loadCert(String certPath) {
        if (certPath == null || certPath.isBlank()) {
            LOG.info("app.aadhaar.uidai-cert-path not set — offline eKYC signature verification is "
                    + "disabled; records will be stored with signatureVerified=false.");
            return null;
        }
        try (FileInputStream in = new FileInputStream(certPath)) {
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            return (X509Certificate) cf.generateCertificate(in);
        } catch (Exception e) {
            // A misconfigured path must not crash the app over a feature that
            // is opt-in and already has an honest "unavailable" state to fall
            // back to — same reasoning as PincodeGeocoder degrading rather
            // than failing a whole request over a third party being down.
            LOG.warn("Could not load UIDAI certificate from '{}' ({}) — offline eKYC signature "
                    + "verification is disabled.", certPath, e.toString());
            return null;
        }
    }

    public AadhaarEkycRecord extractAndStore(CreditApplication application, byte[] zipBytes, String shareCode,
                                             String uploadedByUserId, String uploadedByRole) {
        if (zipBytes == null || zipBytes.length == 0) {
            throw new TransitionException(Failure.BAD_REQUEST, "No file received");
        }
        if (zipBytes.length > MAX_ZIP_BYTES) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "File is larger than " + (MAX_ZIP_BYTES / (1024 * 1024)) + "MB");
        }
        if (application.getStatus().isTerminal()) {
            throw new TransitionException(Failure.CONFLICT,
                    "This application is closed (" + application.getStatus().wireName()
                            + ") and no longer accepts documents");
        }

        ExtractedKyc extracted;
        try {
            extracted = AadhaarOfflineEkycExtractor.extract(zipBytes, shareCode,
                    trustedCert == null ? null : trustedCert.getPublicKey());
        } catch (ExtractionException e) {
            // Same Failure for every extractor Reason: all three are the
            // citizen's to fix (wrong code, wrong file, unrecognised file),
            // never a server error.
            throw new TransitionException(Failure.BAD_REQUEST, e.getMessage());
        }

        AadhaarEkycRecord record = new AadhaarEkycRecord();
        record.setApplicationId(application.getId());
        record.setCitizenId(application.getUserId());
        record.setReferenceId(extracted.referenceId());
        record.setMaskedUid(extracted.maskedUid());
        record.setName(extracted.name());
        record.setDob(extracted.dob());
        record.setGender(extracted.gender());
        record.setCareOf(extracted.careOf());
        record.setAddressOneLine(extracted.address() == null ? null : extracted.address().oneLine());
        record.setEncryptedPhoto(extracted.photo() == null ? null : encryption.encryptBytes(extracted.photo()));
        record.setSignaturePresent(extracted.signaturePresent());
        record.setSignatureVerified(extracted.signatureVerified());
        record.setExtractedAt(LocalDateTime.now());
        record.setUploadedByUserId(uploadedByUserId);
        record.setUploadedByRole(uploadedByRole);

        return records.save(record);
    }

    public List<AadhaarEkycRecord> listFor(String applicationId) {
        return records.findByApplicationIdOrderByExtractedAtDesc(applicationId).stream()
                .peek(r -> r.setEncryptedPhoto(null))   // metadata only — never leak ciphertext in a listing
                .toList();
    }

    public AadhaarEkycRecord requireRecord(String recordId) {
        return records.findById(recordId)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "eKYC record not found"));
    }

    public byte[] photoOf(AadhaarEkycRecord record) {
        if (record.getEncryptedPhoto() == null) {
            throw new TransitionException(Failure.NOT_FOUND, "No photo on this record");
        }
        return encryption.decryptBytes(record.getEncryptedPhoto());
    }

    /** Whether signature verification is switched on at all in this deployment. */
    public boolean verificationAvailable() {
        return trustedCert != null;
    }
}

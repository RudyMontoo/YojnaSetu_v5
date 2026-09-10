package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/**
 * Grants, withdrawals, and the question everything else asks: does this
 * citizen currently permit this?
 *
 * Consent here is a gate, not a log. A record that is written and never
 * consulted is decoration — the value is that
 * {@link #requireConsent} refuses an action outright when permission is
 * absent, which is what makes "purpose-specific and revocable" mean something
 * at runtime rather than on a compliance slide.
 */
@Service
public class ConsentService {

    private final ConsentRepository consents;

    public ConsentService(ConsentRepository consents) {
        this.consents = consents;
    }

    /**
     * Records agreement. Re-granting after a withdrawal writes a new record
     * rather than clearing the old one, so the history stays readable: agreed,
     * withdrew, agreed again is three facts, not one flag flipped twice.
     */
    public Consent grant(String userId, ConsentPurpose purpose, String applicationId, String ip) {
        if (purpose == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "purpose is required");
        }
        // Already agreed and not withdrawn — nothing to record, and writing a
        // duplicate would make the history harder to read for no gain.
        Optional<Consent> existing = activeConsent(userId, purpose, applicationId);
        if (existing.isPresent()) {
            return existing.get();
        }

        Consent consent = new Consent();
        consent.setUserId(userId);
        consent.setPurpose(purpose);
        consent.setApplicationId(applicationId);
        // A copy of the wording, not a pointer to it — see Consent.statement.
        consent.setStatement(purpose.statement());
        consent.setGrantedAt(LocalDateTime.now());
        consent.setIp(ip);
        return consents.save(consent);
    }

    /**
     * Withdraws every active consent for this purpose.
     *
     * @return how many were withdrawn; zero means there was nothing to withdraw
     */
    public int revoke(String userId, ConsentPurpose purpose, String applicationId) {
        List<Consent> active = consents.findByUserIdAndPurpose(userId, purpose).stream()
                .filter(Consent::isActive)
                .filter(c -> applicationId == null || applicationId.equals(c.getApplicationId()))
                .toList();

        LocalDateTime now = LocalDateTime.now();
        active.forEach(c -> {
            c.setRevokedAt(now);
            consents.save(c);
        });
        return active.size();
    }

    public boolean hasConsent(String userId, ConsentPurpose purpose, String applicationId) {
        return activeConsent(userId, purpose, applicationId).isPresent();
    }

    /**
     * Refuses the caller's action when permission is absent.
     *
     * The message names the purpose so the frontend can put the right consent
     * prompt in front of the citizen rather than a generic "forbidden".
     */
    public void requireConsent(String userId, ConsentPurpose purpose, String applicationId) {
        if (!hasConsent(userId, purpose, applicationId)) {
            throw new TransitionException(Failure.FORBIDDEN,
                    "Your consent is needed first: " + purpose.statement());
        }
    }

    public List<Consent> listFor(String userId) {
        return consents.findByUserIdOrderByGrantedAtDesc(userId);
    }

    /**
     * An application-scoped grant also satisfies a request for that purpose on
     * that application; an account-wide grant satisfies any. The reverse is
     * deliberately not true — agreeing to share one loan file is not agreeing
     * to share the next one.
     */
    private Optional<Consent> activeConsent(String userId, ConsentPurpose purpose, String applicationId) {
        return consents.findByUserIdAndPurpose(userId, purpose).stream()
                .filter(Consent::isActive)
                .filter(c -> c.getApplicationId() == null
                        || c.getApplicationId().equals(applicationId))
                .max(Comparator.comparing(Consent::getGrantedAt));
    }
}

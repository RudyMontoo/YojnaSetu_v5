package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Who is allowed to help a citizen with an application, on that citizen's say-so.
 *
 * Assisted access is the difference between this scheme reaching its intended
 * applicants and not reaching them: most people it targets will complete their
 * file sitting next to a CSC operator or an SHG worker, not alone with a
 * browser. But assistance is also the point of highest risk in the whole flow —
 * the helper is holding someone else's identity documents — so the access is
 * granted per application, by the citizen, and is visible and withdrawable by
 * them at any time.
 *
 * Deliberately NOT a substitute for authentication. This authorizes a helper
 * to see and add to a file. It never authorizes them to authenticate as the
 * citizen: an OTP, a biometric, or a consent artefact still happens on the
 * citizen's own phone. A helper who could do those things wouldn't be a helper,
 * they'd be an account takeover with paperwork.
 */
@Service
public class AssistService {

    private final AssistAuthorizationRepository authorizations;
    private final BranchRepRepository helpers;

    public AssistService(AssistAuthorizationRepository authorizations, BranchRepRepository helpers) {
        this.authorizations = authorizations;
        this.helpers = helpers;
    }

    /**
     * The citizen names a helper by the login id printed on that helper's card
     * or badge, not by an internal document id — the id they can actually read
     * off something in front of them.
     */
    public AssistAuthorization grant(CreditApplication application, String citizenId,
                                     String helperRepId, String note) {
        if (helperRepId == null || helperRepId.isBlank()) {
            throw new TransitionException(Failure.BAD_REQUEST, "helperRepId is required");
        }

        BranchRep helper = helpers.findByRepId(helperRepId.trim())
                .filter(BranchRep::isActive)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND,
                        "No active helper found with that ID. Check the ID on their card."));

        // A branch rep already reaches this file through their branch. Recording
        // a citizen-granted authorization for them too would imply the citizen's
        // permission is what lets the lender see their own applicant's file,
        // which is not true and would make a later withdrawal look meaningful
        // when it would change nothing.
        if (!helper.isAssistOnly()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "A branch representative already has access to applications at their branch.");
        }

        Optional<AssistAuthorization> existing = authorizations
                .findByApplicationIdAndHelperIdAndRevokedAtIsNull(application.getId(), helper.getId());
        if (existing.isPresent()) {
            return existing.get();
        }

        AssistAuthorization authorization = new AssistAuthorization();
        authorization.setApplicationId(application.getId());
        authorization.setCitizenId(citizenId);
        authorization.setHelperId(helper.getId());
        authorization.setHelperName(helper.getName());
        authorization.setHelperType(helper.getRepType());
        authorization.setHelperOrganisation(helper.getOrganisation());
        authorization.setGrantedAt(LocalDateTime.now());
        authorization.setNote(note);
        return authorizations.save(authorization);
    }

    /**
     * Withdraws a citizen's authorization. Idempotent: withdrawing something
     * already withdrawn is not an error, because from the citizen's side both
     * requests mean the same thing and both end in the same state.
     */
    public void revoke(String applicationId, String citizenId, String helperId) {
        List<AssistAuthorization> live = authorizations
                .findByApplicationIdOrderByGrantedAtDesc(applicationId).stream()
                .filter(AssistAuthorization::isActive)
                .filter(a -> citizenId.equals(a.getCitizenId()))
                .filter(a -> helperId == null || helperId.equals(a.getHelperId()))
                .toList();

        LocalDateTime now = LocalDateTime.now();
        for (AssistAuthorization authorization : live) {
            authorization.setRevokedAt(now);
            authorizations.save(authorization);
        }
    }

    /** Everyone who has ever been authorized on this file, most recent first. */
    public List<AssistAuthorization> historyFor(String applicationId) {
        return authorizations.findByApplicationIdOrderByGrantedAtDesc(applicationId);
    }

    /** Everything this citizen has granted, across every application. */
    public List<AssistAuthorization> historyForCitizen(String citizenId) {
        return authorizations.findByCitizenIdOrderByGrantedAtDesc(citizenId);
    }

    /** The files a helper is currently authorized to work on. */
    public List<AssistAuthorization> activeFor(String helperId) {
        return authorizations.findByHelperIdAndRevokedAtIsNull(helperId);
    }

    public boolean isAuthorized(String applicationId, String helperId) {
        return authorizations
                .findByApplicationIdAndHelperIdAndRevokedAtIsNull(applicationId, helperId)
                .isPresent();
    }

    /**
     * Gate for anything a helper does to a citizen's file. Refuses rather than
     * filtering, so a caller cannot mistake "you may not" for "there is nothing
     * here".
     */
    public void requireAuthorized(String applicationId, String helperId) {
        if (!isAuthorized(applicationId, helperId)) {
            throw new TransitionException(Failure.FORBIDDEN,
                    "This applicant has not authorized you to help with this application.");
        }
    }
}

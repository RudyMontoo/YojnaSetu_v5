package com.yojnasetu.gateway.notify;

import com.yojnasetu.gateway.credit.BranchRep;
import com.yojnasetu.gateway.credit.BranchRepRepository;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.UserRepository;
import org.springframework.stereotype.Component;

import java.util.Optional;

/**
 * Turns a principal id into somewhere to send a message.
 *
 * This platform has more than one kind of principal and they live in different
 * collections: citizens in {@code users}, and branch reps in
 * {@code branch_reps} — following the same separation {@code Helper} already
 * uses, because staff at a partner institution are not citizens of the
 * platform. Each authenticates with its own document id as the JWT subject.
 *
 * NotificationService originally looked only in {@code users}, so any message
 * addressed to a rep resolved to nobody. Resolution belongs here rather than
 * inline in the service so that adding the next principal type — helpers, CSC
 * operators — is one method, not a scattering of lookups.
 *
 * @param id      the principal id the notification was addressed to
 * @param name    for logs and salutations, never required
 * @param phone   null when none is on file
 * @param email   null when none is on file
 */
public record NotificationRecipient(String id, String name, String phone, String email) {

    @Component
    public static class Resolver {

        private final UserRepository users;
        private final BranchRepRepository branchReps;

        public Resolver(UserRepository users, BranchRepRepository branchReps) {
            this.users = users;
            this.branchReps = branchReps;
        }

        /**
         * @return empty when no principal of any kind holds this id — which the
         *         caller must treat as a fault, not as "nothing to send"
         */
        public Optional<NotificationRecipient> resolve(String principalId) {
            if (principalId == null || principalId.isBlank()) {
                return Optional.empty();
            }

            Optional<User> user = users.findById(principalId);
            if (user.isPresent()) {
                User u = user.get();
                return Optional.of(new NotificationRecipient(
                        u.getId(), null, u.getPhone(), u.getEmail()));
            }

            // Inactive reps are deliberately still resolvable: a message about
            // a file they were working on should reach them, and silently
            // dropping it would look identical to the bug this class fixes.
            Optional<BranchRep> rep = branchReps.findById(principalId);
            return rep.map(r -> new NotificationRecipient(
                    r.getId(), r.getName(), r.getPhone(), r.getEmail()));
        }
    }
}

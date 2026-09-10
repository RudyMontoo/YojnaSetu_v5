package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface AssistAuthorizationRepository extends MongoRepository<AssistAuthorization, String> {

    /** Everyone the citizen has ever authorized on this file, revoked included. */
    List<AssistAuthorization> findByApplicationIdOrderByGrantedAtDesc(String applicationId);

    /** Everything this citizen has ever granted, across all their applications. */
    List<AssistAuthorization> findByCitizenIdOrderByGrantedAtDesc(String citizenId);

    /** The live authorizations a helper is currently working under. */
    List<AssistAuthorization> findByHelperIdAndRevokedAtIsNull(String helperId);

    Optional<AssistAuthorization> findByApplicationIdAndHelperIdAndRevokedAtIsNull(
            String applicationId, String helperId);
}

package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface AaConsentRequestRepository extends MongoRepository<AaConsentRequest, String> {

    Optional<AaConsentRequest> findByConsentHandle(String consentHandle);

    Optional<AaConsentRequest> findFirstByApplicationIdOrderByCreatedAtDesc(String applicationId);
}

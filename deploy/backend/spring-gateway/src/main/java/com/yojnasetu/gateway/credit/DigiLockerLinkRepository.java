package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface DigiLockerLinkRepository extends MongoRepository<DigiLockerLink, String> {

    Optional<DigiLockerLink> findByState(String state);

    Optional<DigiLockerLink> findFirstByApplicationIdAndStatusOrderByCreatedAtDesc(String applicationId, String status);
}

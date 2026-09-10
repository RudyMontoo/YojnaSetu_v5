package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface AadhaarEkycRepository extends MongoRepository<AadhaarEkycRecord, String> {

    List<AadhaarEkycRecord> findByApplicationIdOrderByExtractedAtDesc(String applicationId);

    Optional<AadhaarEkycRecord> findFirstByApplicationIdOrderByExtractedAtDesc(String applicationId);
}

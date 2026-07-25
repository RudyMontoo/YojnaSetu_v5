package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.HelperApplication;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface HelperApplicationRepository extends MongoRepository<HelperApplication, String> {
    /** The applicant's most recent application (to show status / block duplicates). */
    Optional<HelperApplication> findFirstByUserIdOrderByCreatedAtDesc(String userId);

    /** Admin review queue by status, oldest first. */
    List<HelperApplication> findByStatusOrderByCreatedAtAsc(String status);

    long countByStatus(String status);
}

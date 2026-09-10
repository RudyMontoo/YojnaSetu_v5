package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface CreditApplicationRepository extends MongoRepository<CreditApplication, String> {

    List<CreditApplication> findByUserIdOrderByCreatedAtDesc(String userId);

    List<CreditApplication> findByUserIdAndProductId(String userId, String productId);

    List<CreditApplication> findByAssignedPartnerIdOrderBySubmittedAtDesc(String assignedPartnerId);

    List<CreditApplication> findByAssignedPartnerIdAndStatusOrderBySubmittedAtDesc(
            String assignedPartnerId, CreditApplicationStatus status);
}

package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface BranchRepApplicationRepository extends MongoRepository<BranchRepApplication, String> {

    Optional<BranchRepApplication> findFirstByUserIdOrderByCreatedAtDesc(String userId);

    List<BranchRepApplication> findByStatusOrderByCreatedAtAsc(String status);

    long countByStatus(String status);
}

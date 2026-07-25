package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.HelpRequest;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface HelpRequestRepository extends MongoRepository<HelpRequest, String> {
    /** Operator queue — oldest first so nobody waits forever. */
    List<HelpRequest> findByStatusInOrderByCreatedAtAsc(List<String> statuses);

    /** A citizen's own requests, newest first. */
    List<HelpRequest> findByCitizenIdOrderByCreatedAtDesc(String citizenId);

    /** Requests a given helper claimed/resolved, newest first. */
    List<HelpRequest> findByAssignedOperatorIdOrderByUpdatedAtDesc(String assignedOperatorId);

    long countByStatus(String status);
}

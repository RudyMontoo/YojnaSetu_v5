package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface BranchRepRepository extends MongoRepository<BranchRep, String> {

    Optional<BranchRep> findByRepId(String repId);

    /** Everyone who can act on a file at this branch. */
    List<BranchRep> findByPartnerIdAndActiveTrue(String partnerId);
}

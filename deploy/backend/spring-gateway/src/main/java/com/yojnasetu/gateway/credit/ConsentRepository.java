package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ConsentRepository extends MongoRepository<Consent, String> {

    List<Consent> findByUserIdOrderByGrantedAtDesc(String userId);

    List<Consent> findByUserIdAndPurpose(String userId, ConsentPurpose purpose);
}

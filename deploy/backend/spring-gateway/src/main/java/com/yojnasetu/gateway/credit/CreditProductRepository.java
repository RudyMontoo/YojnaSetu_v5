package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface CreditProductRepository extends MongoRepository<CreditProduct, String> {

    List<CreditProduct> findByActiveTrue();

    List<CreditProduct> findByActiveTrueAndProjectType(String projectType);
}

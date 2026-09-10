package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface LoanDocumentRepository extends MongoRepository<LoanDocument, String> {

    List<LoanDocument> findByApplicationIdOrderByUploadedAtDesc(String applicationId);

    long countByApplicationId(String applicationId);

    void deleteByApplicationId(String applicationId);
}

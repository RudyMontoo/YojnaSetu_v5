package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.Application;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ApplicationRepository extends MongoRepository<Application, String> {
    List<Application> findByUserId(String userId);
    List<Application> findByUserIdAndStatus(String userId, String status);
}

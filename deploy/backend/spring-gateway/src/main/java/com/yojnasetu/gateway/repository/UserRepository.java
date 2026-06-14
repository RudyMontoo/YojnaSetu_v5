package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.User;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface UserRepository extends MongoRepository<User, String> {
    Optional<User> findByPhone(String phone);
    boolean existsByPhone(String phone);
}

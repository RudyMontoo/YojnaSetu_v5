package com.yojnasetu.gateway.notify;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface NotificationRepository extends MongoRepository<Notification, String> {

    List<Notification> findByRecipientUserIdOrderByCreatedAtDesc(String recipientUserId);

    List<Notification> findByRecipientUserIdAndReadAtIsNullOrderByCreatedAtDesc(String recipientUserId);

    long countByRecipientUserIdAndReadAtIsNull(String recipientUserId);

    List<Notification> findByApplicationIdOrderByCreatedAtDesc(String applicationId);
}

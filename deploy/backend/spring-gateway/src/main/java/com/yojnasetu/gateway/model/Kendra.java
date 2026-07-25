package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;
import java.util.List;

/**
 * A Jan Seva Kendra registered THROUGH Yojna Sarthi by an approved helper — so it
 * carries the "connected with us" mark on the CSC finder. Stores coordinates so
 * the finder can show the ones nearest a citizen's live location.
 */
@Document(collection = "kendras")
@Data
@NoArgsConstructor
public class Kendra {

    @Id
    private String id;

    private String name;
    private String address;
    private String phone;

    private double lat;
    private double lng;

    private List<String> services;

    /** Which helper registered it (their helper document id). */
    @Indexed
    private String helperId;

    private boolean active = true;

    private LocalDateTime createdAt;
}

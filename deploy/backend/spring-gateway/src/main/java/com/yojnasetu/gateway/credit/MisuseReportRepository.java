package com.yojnasetu.gateway.credit;

import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface MisuseReportRepository extends MongoRepository<MisuseReport, String> {

    List<MisuseReport> findByCitizenIdOrderByCreatedAtDesc(String citizenId);

    List<MisuseReport> findByStatusOrderByCreatedAtDesc(MisuseReport.Status status);
}

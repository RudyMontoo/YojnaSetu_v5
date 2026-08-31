package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.Kendra;
import com.yojnasetu.gateway.repository.HelperRepository;
import com.yojnasetu.gateway.repository.KendraRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Registry of Jan Seva Kendras registered through Yojna Sarthi (Option B). Any
 * signed-in citizen can list the ones nearest their location; approved helpers
 * (ROLE_HELPER) register their own kendra with coordinates.
 */
@RestController
@RequestMapping("/api/v2/kendras")
public class KendraController {

    private final KendraRepository repo;
    private final HelperRepository helperRepo;
    private final FieldEncryptionService encryption;
    private final com.yojnasetu.gateway.service.GeoLabelService geoLabelService;

    public KendraController(KendraRepository repo, HelperRepository helperRepo, FieldEncryptionService encryption,
                             com.yojnasetu.gateway.service.GeoLabelService geoLabelService) {
        this.repo = repo;
        this.helperRepo = helperRepo;
        this.encryption = encryption;
        this.geoLabelService = geoLabelService;
    }

    private static boolean isHelper(Authentication auth) {
        return auth.getAuthorities().stream().anyMatch(a ->
                a.getAuthority().equals("ROLE_HELPER") || a.getAuthority().equals("ROLE_ADMIN"));
    }

    private static boolean isAdmin(Authentication auth) {
        return auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
    }

    /** Great-circle distance in km. */
    private static double haversineKm(double lat1, double lng1, double lat2, double lng2) {
        double r = 6371.0;
        double dLat = Math.toRadians(lat2 - lat1), dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    private static Map<String, Object> view(Kendra k, Double distanceKm) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", k.getId());
        m.put("name", k.getName());
        m.put("address", k.getAddress());
        m.put("phone", k.getPhone());
        m.put("lat", k.getLat());
        m.put("lng", k.getLng());
        m.put("services", k.getServices());
        m.put("connected", true);   // every registered kendra is part of our network
        if (distanceKm != null) m.put("distanceKm", Math.round(distanceKm * 10) / 10.0);
        return m;
    }

    /** Registered kendras nearest a location, sorted closest-first. */
    @GetMapping("/nearby")
    public ResponseEntity<?> nearby(@RequestParam double lat, @RequestParam double lng,
                                    @RequestParam(defaultValue = "20") int limit) {
        List<Map<String, Object>> out = repo.findByActiveTrue().stream()
                .sorted(Comparator.comparingDouble(k -> haversineKm(lat, lng, k.getLat(), k.getLng())))
                .limit(Math.max(1, Math.min(limit, 100)))
                .map(k -> view(k, haversineKm(lat, lng, k.getLat(), k.getLng())))
                .toList();
        // Best-effort — the kendra list still renders if this lookup fails.
        String locationLabel = geoLabelService.label(lat, lng);
        Map<String, Object> body = new HashMap<>();
        body.put("kendras", out);
        body.put("locationLabel", locationLabel);
        return ResponseEntity.ok(body);
    }

    public record RegisterKendra(String name, String address, String phone,
                                 Double lat, Double lng, List<String> services) {}

    /** Helper registers their own kendra (with coordinates). */
    @PostMapping
    public ResponseEntity<?> register(Authentication auth, @RequestBody RegisterKendra req) {
        if (!isHelper(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Helpers only"));
        if (req.name() == null || req.name().isBlank() || req.lat() == null || req.lng() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "name, lat and lng are required"));
        }
        Kendra k = new Kendra();
        k.setName(req.name().trim());
        k.setAddress(req.address() != null ? req.address().trim() : null);
        k.setPhone(req.phone() != null ? req.phone().trim() : null);
        k.setLat(req.lat());
        k.setLng(req.lng());
        k.setServices(req.services());
        k.setHelperId(auth.getName());
        k.setActive(true);
        k.setCreatedAt(LocalDateTime.now());
        k = repo.save(k);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("success", true, "id", k.getId()));
    }

    /** A helper's own registered kendras. */
    @GetMapping("/mine")
    public ResponseEntity<?> mine(Authentication auth) {
        if (!isHelper(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Helpers only"));
        return ResponseEntity.ok(Map.of("kendras", repo.findByHelperId(auth.getName()).stream().map(k -> view(k, null)).toList()));
    }

    /** Deactivate a kendra: the OWNING helper, or an ADMIN (oversight over the network). */
    @PostMapping("/{id}/deactivate")
    public ResponseEntity<?> deactivate(Authentication auth, @PathVariable String id) {
        if (!isHelper(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Helpers only"));
        return repo.findById(id).<ResponseEntity<?>>map(k -> {
            if (!isAdmin(auth) && !auth.getName().equals(k.getHelperId())) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Not your kendra"));
            }
            k.setActive(false);
            repo.save(k);
            return ResponseEntity.ok(Map.of("success", true));
        }).orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Kendra not found")));
    }

    /** Admin: every kendra (active + inactive) with the registering helper's name. */
    @GetMapping("/all")
    public ResponseEntity<?> all(Authentication auth) {
        if (!isAdmin(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        List<Map<String, Object>> out = repo.findAll().stream().map(k -> {
            Map<String, Object> m = view(k, null);
            m.put("active", k.isActive());
            m.put("helperId", k.getHelperId());
            String hn = (k.getHelperId() == null) ? null
                    : helperRepo.findById(k.getHelperId()).map(h -> encryption.decrypt(h.getName())).orElse(null);
            m.put("helperName", hn);
            return m;
        }).toList();
        return ResponseEntity.ok(Map.of("kendras", out));
    }
}

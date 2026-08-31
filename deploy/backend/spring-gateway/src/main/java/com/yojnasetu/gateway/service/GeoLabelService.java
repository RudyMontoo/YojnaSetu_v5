package com.yojnasetu.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Locale;

/**
 * Reverse-geocodes a lat/lng into a human-readable place name ("Patna,
 * Bihar") via OpenStreetMap's Nominatim, so a citizen can see WHERE the app
 * thinks they are, not just a list of distances. Proxied server-side —
 * Nominatim has no CORS headers for browser calls (verified via curl), and
 * its usage policy requires a custom User-Agent identifying the app.
 */
@Service
public class GeoLabelService {

    private static final Logger LOG = LoggerFactory.getLogger(GeoLabelService.class);
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** Returns e.g. "Patna, Bihar", or null if the lookup fails — callers must not block on this. */
    public String label(double lat, double lng) {
        try {
            String url = String.format(Locale.US,
                    "https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=%f&lon=%f&zoom=10&addressdetails=1",
                    lat, lng);
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(5))
                    .header("User-Agent", "YojnaSarthi/1.0 (welfare-scheme discovery app; contact: rudra@yojnasetu.in)")
                    .GET()
                    .build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) return null;

            JsonNode addr = MAPPER.readTree(res.body()).path("address");
            String city = firstNonBlank(addr, "city", "town", "village", "county");
            String state = addr.path("state").asText(null);
            if (city != null && state != null) return city + ", " + state;
            if (state != null) return state;
            return city;
        } catch (Exception e) {
            LOG.warn("Reverse geocode failed for ({}, {}): {}", lat, lng, e.toString());
            return null;
        }
    }

    private static String firstNonBlank(JsonNode node, String... fields) {
        for (String f : fields) {
            String v = node.path(f).asText(null);
            if (v != null && !v.isBlank()) return v;
        }
        return null;
    }
}

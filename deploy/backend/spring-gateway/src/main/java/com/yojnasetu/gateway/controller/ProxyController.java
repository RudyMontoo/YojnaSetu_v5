package com.yojnasetu.gateway.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.util.UriComponentsBuilder;
import reactor.core.publisher.Mono;

import java.util.Map;

/**
 * Proxy Controller — Forwards all AI requests to the FastAPI AI Hub.
 * Spring Boot handles auth, CORS, logging; FastAPI does the heavy AI lifting.
 */
@RestController
@RequestMapping("/api")
public class ProxyController {

    private final WebClient webClient;

    public ProxyController(@Value("${app.fastapi.url}") String fastapiUrl) {
        this.webClient = WebClient.builder()
                .baseUrl(fastapiUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    // ── Health ─────────────────────────────────────────────────────────────────
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "service", "Yojna Setu Gateway",
                "status", "ok",
                "version", "2.0.0"));
    }

    // ── Chat ───────────────────────────────────────────────────────────────────
    @PostMapping("/chat")
    public Mono<ResponseEntity<Object>> chat(@RequestBody Object body) {
        return forward(HttpMethod.POST, "/chat/", body);
    }

    @PostMapping("/chat/stream")
    public Mono<ResponseEntity<Object>> chatStream(@RequestBody Object body) {
        return forward(HttpMethod.POST, "/chat/stream", body);
    }

    @DeleteMapping("/chat/session/{sessionId}")
    public Mono<ResponseEntity<Object>> clearChatSession(@PathVariable String sessionId) {
        return forward(HttpMethod.DELETE, "/chat/session/" + sessionId, null);
    }

    // ── Agent Interview ────────────────────────────────────────────────────────
    @PostMapping("/agent/start")
    public Mono<ResponseEntity<Object>> agentStart(@RequestBody Object body) {
        return forward(HttpMethod.POST, "/agent/start", body);
    }

    @PostMapping("/agent/answer")
    public Mono<ResponseEntity<Object>> agentAnswer(@RequestBody Object body) {
        return forward(HttpMethod.POST, "/agent/answer", body);
    }

    @DeleteMapping("/agent/session/{sessionId}")
    public Mono<ResponseEntity<Object>> clearAgentSession(@PathVariable String sessionId) {
        return forward(HttpMethod.DELETE, "/agent/session/" + sessionId, null);
    }

    // ── Status Tracker ─────────────────────────────────────────────────────────
    @PostMapping("/status/check")
    public Mono<ResponseEntity<Object>> statusCheck(@RequestBody Object body) {
        return forward(HttpMethod.POST, "/status/check", body);
    }

    @GetMapping("/status/schemes")
    public Mono<ResponseEntity<Object>> statusSchemes() {
        return forward(HttpMethod.GET, "/status/schemes", null);
    }

    // ── Apply Guide ────────────────────────────────────────────────────────────
    @GetMapping("/schemes")
    public Mono<ResponseEntity<Object>> listSchemes() {
        return forward(HttpMethod.GET, "/apply/schemes", null);
    }

    @GetMapping("/apply/guide")
    public Mono<ResponseEntity<Object>> applyGuide(
            @RequestParam String scheme_key,
            @RequestParam(required = false) String state,
            @RequestParam(required = false) String language) {

        String uri = UriComponentsBuilder.fromPath("/apply/guide")
                .queryParam("scheme_key", scheme_key)
                .queryParamIfPresent("state", java.util.Optional.ofNullable(state))
                .queryParamIfPresent("language", java.util.Optional.ofNullable(language))
                .build().toUriString();

        return forward(HttpMethod.GET, uri, null);
    }

    // ── Help & Discovery ───────────────────────────────────────────────────────
    @GetMapping("/help/csc/nearby")
    public Mono<ResponseEntity<Object>> cscNearby(
            @RequestParam double lat,
            @RequestParam double lon,
            @RequestParam(defaultValue = "10.0") double radius_km,
            @RequestParam(required = false) String state) {

        String uri = UriComponentsBuilder.fromPath("/help/csc/nearby")
                .queryParam("lat", lat)
                .queryParam("lon", lon)
                .queryParam("radius_km", radius_km)
                .queryParamIfPresent("state", java.util.Optional.ofNullable(state))
                .build().toUriString();

        return forward(HttpMethod.GET, uri, null);
    }

    @GetMapping("/help/doc/guide")
    public Mono<ResponseEntity<Object>> docGuide(
            @RequestParam String document,
            @RequestParam(required = false) String state) {

        String uri = UriComponentsBuilder.fromPath("/help/doc/guide")
                .queryParam("document", document)
                .queryParamIfPresent("state", java.util.Optional.ofNullable(state))
                .build().toUriString();

        return forward(HttpMethod.GET, uri, null);
    }

    // ── Generic Proxy Helper ───────────────────────────────────────────────────
    private Mono<ResponseEntity<Object>> forward(HttpMethod method, String path, Object body) {
        // Two separate branches to satisfy WebClient's type hierarchy:
        // bodyValue() lives on RequestBodySpec; retrieve() on RequestHeadersSpec.
        var retrieve = (body != null)
                ? webClient.method(method).uri(path).bodyValue(body).retrieve()
                : webClient.method(method).uri(path).retrieve();

        return retrieve
                .onStatus(status -> status.isError(),
                        res -> res.bodyToMono(String.class)
                                .map(b -> new RuntimeException("FastAPI error: " + b)))
                .bodyToMono(Object.class)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> Mono.just(
                        ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                                .body(Map.of("error", "AI Hub unavailable: " + e.getMessage()))));
    }
}

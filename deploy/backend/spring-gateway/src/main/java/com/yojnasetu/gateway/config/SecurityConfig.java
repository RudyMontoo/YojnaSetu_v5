package com.yojnasetu.gateway.config;

import com.yojnasetu.gateway.security.JwtAuthFilter;
import com.yojnasetu.gateway.security.RateLimitFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

/**
 * Per ADR-001: no more UserDetailsService/AuthenticationManager/password
 * encoder beans — those were for the username+password flow this rewrite
 * removes. OTP verification (OtpService) and JWT (JwtAuthFilter) replace
 * them entirely; there's no Spring Security "authentication provider" in
 * the traditional sense, just a filter that trusts a validated JWT.
 *
 * CSRF stays disabled (unchanged from before this rewrite) — SameSite=Strict
 * on both cookies (see AuthController) is the baseline protection; a full
 * CSRF-token scheme is not part of this phase's scope.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;
    private final RateLimitFilter rateLimitFilter;

    @Value("${app.cors.allowed-origins}")
    private String allowedOrigins;

    public SecurityConfig(JwtAuthFilter jwtAuthFilter, RateLimitFilter rateLimitFilter) {
        this.jwtAuthFilter = jwtAuthFilter;
        this.rateLimitFilter = rateLimitFilter;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .csrf(AbstractHttpConfigurer::disable)
                // Explicit security headers (security-audit prompt 3.4). Spring
                // defaults already set X-Content-Type-Options + X-Frame-Options;
                // this adds HSTS and a restrictive CSP on top.
                .headers(headers -> headers
                        .httpStrictTransportSecurity(hsts -> hsts
                                .includeSubDomains(true)
                                .maxAgeInSeconds(31536000))
                        .frameOptions(frame -> frame.deny())
                        .contentSecurityPolicy(csp -> csp
                                .policyDirectives("default-src 'self'; frame-ancestors 'none'")))
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/v2/auth/**",
                                "/api/health",
                                "/api/chat/**", // proxied to FastAPI, public for demo per existing ProxyController
                                "/api/agent/**",
                                "/api/schemes/**",
                                "/api/apply/**",
                                "/api/status/**",
                                "/api/help/**",
                                "/internal/**") // FastAPI service-to-service — key-checked in the controller itself, not here
                        .permitAll()
                        .anyRequest().authenticated())
                .addFilterBefore(rateLimitFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        List<String> origins = Arrays.asList(allowedOrigins.split(","));
        // Security-audit prompt 3.6 / 5: with allowCredentials=true, a wildcard
        // pattern like "https://*.vercel.app" would let ANY Vercel-hosted site
        // ride a logged-in user's cookies. Restrict to the explicitly-configured
        // origins (app.cors.allowed-origins) plus localhost for dev only.
        config.setAllowedOriginPatterns(List.of("http://localhost:*"));
        config.setAllowedOrigins(origins.stream().map(String::trim).toList());
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true); // required for httpOnly cookies to be sent cross-origin (frontend on a different port)
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}

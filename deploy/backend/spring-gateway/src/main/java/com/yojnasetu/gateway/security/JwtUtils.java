package com.yojnasetu.gateway.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.NoSuchAlgorithmException;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.Date;

/**
 * RS256 JWT, per CLAUDE.md's L2 security layer: "JWT RS256, stored in
 * httpOnly cookies only." RS256 (asymmetric) rather than the old HS256 —
 * lets other services verify tokens with just the public key, without
 * holding the signing secret.
 *
 * Keys are PEM files (PKCS8 private, X509 public) at the paths configured
 * by JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH. If they don't exist at
 * startup, a warning is logged and a dev-only ephemeral keypair is
 * generated in memory instead — tokens issued that way are invalid after a
 * restart, which is fine for local dev and actively bad in prod, so this
 * is logged loudly, not silently.
 */
@Component
public class JwtUtils {

    @Value("${app.jwt.private-key-path:}")
    private String privateKeyPath;

    @Value("${app.jwt.public-key-path:}")
    private String publicKeyPath;

    @Value("${app.jwt.access-token-expiry-minutes:60}")
    private long accessTokenExpiryMinutes;

    @Value("${app.jwt.refresh-token-expiry-days:7}")
    private long refreshTokenExpiryDays;

    private PrivateKey privateKey;
    private PublicKey publicKey;

    @PostConstruct
    public void init() throws NoSuchAlgorithmException, InvalidKeySpecException, IOException {
        if (privateKeyPath != null && !privateKeyPath.isBlank() && Files.exists(Path.of(privateKeyPath))
                && publicKeyPath != null && !publicKeyPath.isBlank() && Files.exists(Path.of(publicKeyPath))) {
            this.privateKey = loadPrivateKey(privateKeyPath);
            this.publicKey = loadPublicKey(publicKeyPath);
        } else {
            System.err.println(
                    "WARNING: JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH not configured or files missing. "
                            + "Generating an EPHEMERAL in-memory RSA keypair — tokens will be invalid after restart. "
                            + "This is fine for local dev, NEVER acceptable in production. "
                            + "Generate real keys with: openssl genpkey -algorithm RSA -out private.pem -pkeyopt rsa_keygen_bits:2048 "
                            + "&& openssl rsa -pubout -in private.pem -out public.pem");
            var kp = java.security.KeyPairGenerator.getInstance("RSA");
            kp.initialize(2048);
            var pair = kp.generateKeyPair();
            this.privateKey = pair.getPrivate();
            this.publicKey = pair.getPublic();
        }
    }

    private PrivateKey loadPrivateKey(String path) throws IOException, NoSuchAlgorithmException, InvalidKeySpecException {
        String pem = Files.readString(Path.of(path))
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s", "");
        byte[] decoded = Base64.getDecoder().decode(pem);
        return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(decoded));
    }

    private PublicKey loadPublicKey(String path) throws IOException, NoSuchAlgorithmException, InvalidKeySpecException {
        String pem = Files.readString(Path.of(path))
                .replace("-----BEGIN PUBLIC KEY-----", "")
                .replace("-----END PUBLIC KEY-----", "")
                .replaceAll("\\s", "");
        byte[] decoded = Base64.getDecoder().decode(pem);
        return KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(decoded));
    }

    public String generateAccessToken(String userId, String role) {
        Date now = new Date();
        return Jwts.builder()
                .subject(userId)
                .claim("role", role)
                .claim("type", "access")
                .issuedAt(now)
                .expiration(new Date(now.getTime() + accessTokenExpiryMinutes * 60_000))
                .signWith(privateKey, Jwts.SIG.RS256)
                .compact();
    }

    public String generateRefreshToken(String userId) {
        Date now = new Date();
        return Jwts.builder()
                .subject(userId)
                .claim("type", "refresh")
                .issuedAt(now)
                .expiration(new Date(now.getTime() + refreshTokenExpiryDays * 86_400_000))
                .signWith(privateKey, Jwts.SIG.RS256)
                .compact();
    }

    public Claims parseClaims(String token) {
        return Jwts.parser().verifyWith(publicKey).build().parseSignedClaims(token).getPayload();
    }

    /** Returns userId if valid, null otherwise — never throws. */
    public String validateAndGetUserId(String token, String expectedType) {
        try {
            Claims claims = parseClaims(token);
            if (!expectedType.equals(claims.get("type"))) return null;
            return claims.getSubject();
        } catch (JwtException | IllegalArgumentException e) {
            return null;
        }
    }

    public long getAccessTokenExpirySeconds() {
        return accessTokenExpiryMinutes * 60;
    }

    public long getRefreshTokenExpirySeconds() {
        return refreshTokenExpiryDays * 86_400;
    }
}

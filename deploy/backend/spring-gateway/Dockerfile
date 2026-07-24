# Spring Boot gateway — Cloud Run container, multi-stage so it builds from
# source (no separate `mvn package` needed; works with `gcloud run deploy --source`).

# ---- build stage ----
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY pom.xml ./
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q clean package -DskipTests

# ---- run stage ----
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /build/target/gateway-2.0.0.jar app.jar
# JWT signing keys (RS256), referenced by JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH.
# Baked into this PRIVATE image because Spring otherwise generates an EPHEMERAL
# keypair that invalidates every token on restart. TRADEOFF: the private key lives
# in the ACR image layer — acceptable for a private registry + demo, but rotate to
# a Container Apps secret-volume before real users (see deploy/azure/DEPLOY.md).
COPY keys/jwt_private.pem keys/jwt_public.pem /app/keys/
# Cloud Run sets $PORT; Spring must bind it (server.port). Xmx tuned for a
# small Cloud Run instance (512Mi); raise with the instance size.
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["sh", "-c", "java -Xmx350m -Dserver.port=${PORT:-8080} -jar app.jar"]

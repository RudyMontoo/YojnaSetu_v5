FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/gateway-2.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-Xmx300m", "-jar", "app.jar"]

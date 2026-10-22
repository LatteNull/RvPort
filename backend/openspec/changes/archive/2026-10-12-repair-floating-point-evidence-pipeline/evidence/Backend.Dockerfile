ARG RUNTIME_IMAGE=registry.example.invalid/project/rvport-backend:fp-evidence-repair-runtime
FROM ${RUNTIME_IMAGE}
COPY rvport-backend-0.1.0-SNAPSHOT.jar /app/backend/rvport-backend.jar

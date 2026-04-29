FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema:
# - build-essential: compilar wheels nativos
# - curl/ca-certificates: para descargar Docker CLI estático
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (estático) para que /api/execute-action pueda correr:
#   docker restart <container>
#   docker logs <container>
#
# Evita depender del paquete `docker.io` (no siempre disponible/igual en slim).
ARG DOCKER_CLI_VERSION=27.0.3
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
    -o /tmp/docker.tgz \
  && tar -xzf /tmp/docker.tgz -C /tmp \
  && mv /tmp/docker/docker /usr/local/bin/docker \
  && chmod +x /usr/local/bin/docker \
  && rm -rf /tmp/docker /tmp/docker.tgz

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

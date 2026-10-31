#install python en pip
ARG BUILD_FROM
ARG BUILD_VERSION
ARG TARGETARCH

# Pinned Ubuntu base images (ignore BUILD_FROM from Supervisor to ensure Ubuntu, not Alpine)
# Digests resolved from ghcr.io registry manifests for tag 10.0.5 on 2026-10-25; Ubuntu 24.04, Python 3.12.
FROM ghcr.io/hassio-addons/ubuntu-base/aarch64:10.0.5@sha256:6e729479f273b9f83165e43f80a7574d19c5f490a3df80d7d0830c5369cbaa04 AS base-arm64
FROM ghcr.io/hassio-addons/ubuntu-base/amd64:10.0.5@sha256:0b873304745adf7e57bfa0e96fbc4eed0117c1bf3597b4f0d5a42c2987bc5aa8 AS base-amd64

# Select base matching target architecture (TARGETARCH is arm64 or amd64 from BuildKit)
FROM base-${TARGETARCH} AS final-base

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Python and pip in a single layer
# Using python3 instead of python3-minimal for better pip package compatibility
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app_data
COPY rootfs /
# COPY ingress.conf /etc/nginx/http.d/

# Pinned Predbat v9.5.0 code (vendored from springfall2008/batpred @ 0cfceaaa, see VENDOR.txt).
# The build fails if any vendored file does not match MANIFEST.sha256.
COPY vendor /opt/predbat/vendor
COPY MANIFEST.sha256 VENDOR.txt /opt/predbat/
RUN cd /opt/predbat/vendor \
    && sha256sum --strict -c --quiet ../MANIFEST.sha256 \
    && test "$(find . -type f | wc -l)" -eq "$(wc -l < ../MANIFEST.sha256)" \
    && chmod -R a-w /opt/predbat

COPY requirements.txt /tmp/
RUN pip install --break-system-packages --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.txt

# Start app
RUN chmod a+x /run.sh

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="kamien5 (https://github.com/kamien5)" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="kamien5" \
    org.opencontainers.image.authors="kamien5 (fork of springfall2008/predbat_addon by Trefor Southwell)" \
    org.opencontainers.image.licenses="NOASSERTION" \
    org.opencontainers.image.url="https://github.com/kamien5/predbat_addon" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

#CMD [ "/run.sh" ]

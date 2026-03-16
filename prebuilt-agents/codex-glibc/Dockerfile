FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CARGO_HOME=/opt/cargo
ENV RUSTUP_HOME=/opt/rustup
ENV PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential \
      pkg-config \
      libssl-dev \
      libcap-dev \
      curl \
      git \
      ca-certificates \
      python3 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/cargo /opt/rustup /work \
    && chmod -R 0777 /opt/cargo /opt/rustup /work

RUN curl --proto '=https' --tlsv1.2 -fL https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && /bin/sh /tmp/rustup-init.sh -y --no-modify-path \
    && rm -f /tmp/rustup-init.sh

WORKDIR /work

COPY build-codex-glibc.sh /usr/local/bin/build-codex-glibc
RUN chmod +x /usr/local/bin/build-codex-glibc

ENTRYPOINT ["/usr/local/bin/build-codex-glibc"]

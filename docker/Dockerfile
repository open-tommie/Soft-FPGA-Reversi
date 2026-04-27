FROM ubuntu:24.04

ARG PICO_SDK_TAG=2.2.0
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git python3 \
        build-essential cmake ninja-build pkg-config \
        gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib \
        libusb-1.0-0-dev \
        ccache \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch ${PICO_SDK_TAG} --depth 1 \
        https://github.com/raspberrypi/pico-sdk.git /opt/pico-sdk \
    && git -C /opt/pico-sdk submodule update --init --depth 1

ENV PICO_SDK_PATH=/opt/pico-sdk \
    PICO_PLATFORM=rp2350 \
    PICO_BOARD=pico2 \
    CCACHE_DIR=/ccache \
    PATH=/usr/lib/ccache:/usr/local/bin:/usr/bin:/bin

RUN if ! getent group ${USER_GID} >/dev/null; then groupadd -g ${USER_GID} dev; fi \
    && if ! id -u ${USER_UID} >/dev/null 2>&1; then \
         useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash dev; \
       fi \
    && mkdir -p /ccache && chown -R ${USER_UID}:${USER_GID} /ccache

USER ${USER_UID}:${USER_GID}
WORKDIR /work
CMD ["bash"]

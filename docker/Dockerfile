FROM ubuntu:24.04

ARG PICO_SDK_TAG=2.2.0
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git python3 python3-venv python3-dev libpython3-dev \
        build-essential cmake ninja-build pkg-config \
        libusb-1.0-0-dev libhidapi-dev libftdi-dev \
        autoconf automake libtool texinfo \
        flex bison libfl-dev help2man perl perl-doc \
        usbutils \
        ccache \
    && rm -rf /var/lib/apt/lists/*

# arm-none-eabi-gcc は Pico VSCode extension が配る xPack 14.2 に揃える
# (apt の 13.2 だと newlib 差で Verilator ランタイムがリンクできない)
ARG XPACK_ARM_GCC_VER=15.2.1-1.1
RUN curl -fsSL "https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v${XPACK_ARM_GCC_VER}/xpack-arm-none-eabi-gcc-${XPACK_ARM_GCC_VER}-linux-x64.tar.gz" \
        | tar -xz -C /opt \
    && ln -s /opt/xpack-arm-none-eabi-gcc-${XPACK_ARM_GCC_VER} /opt/arm-gcc

RUN git clone --branch ${PICO_SDK_TAG} --depth 1 \
        https://github.com/raspberrypi/pico-sdk.git /opt/pico-sdk \
    && git -C /opt/pico-sdk submodule update --init --depth 1

ARG OPENOCD_REV=acff23ffd100479d6481a1155123774b79a990b9
RUN mkdir /tmp/openocd && cd /tmp/openocd \
    && git init -q \
    && git remote add origin https://github.com/raspberrypi/openocd.git \
    && git fetch --depth 1 -q origin ${OPENOCD_REV} \
    && git checkout -q FETCH_HEAD \
    && git submodule update --init --depth 1 \
    && ./bootstrap \
    && ./configure --enable-cmsis-dap --enable-internal-jimtcl \
                   --disable-werror --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install \
    && cd / && rm -rf /tmp/openocd

ARG VERILATOR_TAG=v5.048
RUN git clone --branch ${VERILATOR_TAG} --depth 1 \
        https://github.com/verilator/verilator.git /tmp/verilator \
    && cd /tmp/verilator \
    && autoconf \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install \
    && cd / && rm -rf /tmp/verilator

# bloaty: ELF サイズ調査ツール (Google)。Ubuntu 24.04 apt に無いのでソースビルド。
# v1.1 (2020) は古すぎてビルド通らないことがあるため main の固定 SHA を採用。
ARG BLOATY_REV=04bca29ffdd781de1bff5b751e0d5459c844a596
RUN mkdir /tmp/bloaty && cd /tmp/bloaty \
    && git init -q \
    && git remote add origin https://github.com/google/bloaty.git \
    && git fetch --depth 1 -q origin ${BLOATY_REV} \
    && git checkout -q FETCH_HEAD \
    && git submodule update --init --depth 1 \
    && cmake -B build -G Ninja -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j"$(nproc)" \
    && cmake --install build \
    && cd / && rm -rf /tmp/bloaty

ENV PICO_SDK_PATH=/opt/pico-sdk \
    PICO_PLATFORM=rp2350 \
    PICO_BOARD=pico2 \
    PICO_TOOLCHAIN_PATH=/opt/arm-gcc \
    CCACHE_DIR=/ccache \
    PATH=/usr/lib/ccache:/opt/arm-gcc/bin:/usr/local/bin:/usr/bin:/bin

RUN if ! getent group ${USER_GID} >/dev/null; then groupadd -g ${USER_GID} dev; fi \
    && if ! id -u ${USER_UID} >/dev/null 2>&1; then \
         useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash dev; \
       fi \
    && mkdir -p /ccache && chown -R ${USER_UID}:${USER_GID} /ccache

USER ${USER_UID}:${USER_GID}
WORKDIR /work
CMD ["bash"]

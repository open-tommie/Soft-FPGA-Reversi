FROM ubuntu:24.04

ARG PICO_SDK_TAG=2.2.0
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git python3 \
        build-essential cmake ninja-build pkg-config \
        gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib \
        libusb-1.0-0-dev libhidapi-dev libftdi-dev \
        autoconf automake libtool texinfo \
        flex bison libfl-dev help2man perl perl-doc \
        usbutils \
        ccache \
    && rm -rf /var/lib/apt/lists/*

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

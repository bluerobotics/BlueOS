FROM debian:bullseye-slim

#COPY 2021-10-30-raspios-bullseye-armhf-lite.img 2021-10-30-raspios-bullseye-armhf-lite.img
RUN apt update && apt install -y unzip xz-utils tar wget
RUN wget https://developer.arm.com/-/media/Files/downloads/gnu-a/10.3-2021.07/binrel/gcc-arm-10.3-2021.07-x86_64-arm-none-linux-gnueabihf.tar.xz
RUN tar -xvf gcc-arm-10.3-2021.07-x86_64-arm-none-linux-gnueabihf.tar.xz
ENV PATH="$PWD/gcc-arm-10.3-2021.07-x86_64-arm-none-linux-gnueabihf/bin:${PATH}"

COPY setup.sh /usr/bin/setup.sh
COPY build.sh /usr/bin/build.sh
RUN chmod +x /usr/bin/setup.sh
RUN chmod +x /usr/bin/build.sh

RUN apt update
RUN apt install -y bc build-essential cpio fakeroot libssl-dev ncurses-dev git make sudo bison flex kmod
RUN mkdir -p /tmp/run
COPY bcm2711_navigator_defconfig /tmp/
CMD cd /tmp/run && setup.sh
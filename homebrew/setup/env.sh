#! /bin/bash

export NAOMI_BASE=/opt/toolchains/naomi
export NAOMI_SH_BASE=${NAOMI_BASE}/sh-elf
export NAOMI_ARM_BASE=${NAOMI_BASE}/arm-eab
export NAOMI_SH_GCC_VER=9.3.0
export NAOMI_ARM_GCC_VER=8.4.0

export NAOMI_SH_CC=${NAOMI_SH_BASE}/bin/sh-elf-gcc
export NAOMI_SH_LD=${NAOMI_SH_BASE}/bin/sh-elf-ld
export NAOMI_SH_AS=${NAOMI_SH_BASE}/bin/sh-elf-as
export NAOMI_SH_OBJCOPY=${NAOMI_SH_BASE}/bin/sh-elf-objcopy
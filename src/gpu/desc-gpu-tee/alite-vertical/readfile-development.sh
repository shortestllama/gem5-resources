#!/bin/sh
# DEVELOPMENT ONLY: full legitimate measurement of a smaller 2 MiB EPM.
# Production/32 MiB test remains readfile.sh, unchanged.
set -eu
insmod /root/keystone-driver.ko
/sbin/desc-runner -e 2M /root/amd-square-enclave
/sbin/m5 exit

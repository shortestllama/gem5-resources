#!/bin/sh
set -eu
insmod /root/keystone-driver.ko
/sbin/desc-runner -e 32M /root/amd-square-enclave
/sbin/m5 exit

#!/usr/bin/env bash
# Skrypt do stawiania interfejsu tantap
sudo ip tuntap add dev tap0 mode tap
sudo ip link set dev tap0 up
sudo ip addr add 10.0.0.1/24 dev tap0
ip addr | grep tap0

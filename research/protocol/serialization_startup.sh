#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io git
systemctl enable --now docker
install -d -m 1777 /srv/serialization
touch /srv/serialization/startup-ready

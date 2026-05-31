#!/usr/bin/env bash
#
# Canopus init wrapper: run the standard Superset init (migrations, admin user,
# roles, examples) and then apply the Canopus start-page setup.
#
set -e

/app/docker/docker-init.sh

echo "######################################################################"
echo "Canopus post-init -- configuring start dashboard"
echo "######################################################################"
python /app/docker/canopus/postinit.py

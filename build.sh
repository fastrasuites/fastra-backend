#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

# For Inventory
python manage.py create_default_locations

python manage.py migrate
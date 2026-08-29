#!/usr/bin/env sh
set -eu

env_file="${1:-.env.staging}"

if [ ! -f "$env_file" ]; then
  echo "Missing staging environment file: $env_file" >&2
  exit 1
fi

if grep -Eq '(^|=)(replace_with_|CHANGE_ME)' "$env_file"; then
  echo "Replace every example secret in $env_file before deployment." >&2
  exit 1
fi

for variable in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD SECRET_KEY REDIS_PASSWORD; do
  if ! grep -Eq "^${variable}=.+" "$env_file"; then
    echo "Missing required value: $variable" >&2
    exit 1
  fi
done

echo "Staging environment file passed the required-value check."

#!/usr/bin/env sh
# Builds .env.staging ON THE SERVER from .env.staging.example.
#
#  * the database password, secret key and Redis password are generated here
#    as random hex, so they never appear in chat, git or a laptop;
#  * the inference provider key is read from a private file (see below) and
#    that file is deleted afterwards;
#  * nginx is moved to port 8080 so Caddy can own ports 80 and 443;
#  * knowledge graph generation and database semantic search are switched on.
#
# Run from the project folder on the server:   sh scripts/make-staging-env.sh
#
# It never overwrites an existing .env.staging: replacing it would change every
# secret and break a database that already exists.
set -eu

cd "$(dirname "$0")/.."

target=".env.staging"
template=".env.staging.example"
key_file="${INFERENCE_KEY_FILE:-$HOME/.inference_key}"

if [ -f "$target" ]; then
  echo "$target already exists, so nothing was changed." >&2
  echo "Delete it yourself first only if you really want all-new secrets." >&2
  exit 1
fi

if [ ! -f "$template" ]; then
  echo "Missing $template. Run this from the project folder." >&2
  exit 1
fi

if [ ! -s "$key_file" ] || ! grep -Eq '^INFERENCE_API_KEY=.+' "$key_file"; then
  echo "Missing or empty provider key file: $key_file" >&2
  echo "It must contain one line: INFERENCE_API_KEY=your-key" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required to generate random secrets." >&2
  exit 1
fi

# Hex only: these values end up inside postgresql:// and redis:// URLs, where
# characters such as @ or / would break the connection string.
random_secret() {
  openssl rand -hex 32
}

umask 077

{
  sed \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random_secret)|" \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(random_secret)|" \
    -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(random_secret)|" \
    -e "s|^NGINX_HTTP_PORT=.*|NGINX_HTTP_PORT=8080|" \
    -e '/^INFERENCE_API_KEY=/d' \
    "$template"
  grep -E '^INFERENCE_API_KEY=.+' "$key_file" | head -n 1
  echo ""
  echo "# Switched on for staging."
  echo "ENABLE_KNOWLEDGE_GRAPH_GENERATION=true"
  echo "ENABLE_DATABASE_SEMANTIC_SEARCH=true"
} > "$target"

chmod 600 "$target"
rm -f "$key_file"

echo "Created $target (permissions 600)."
echo "Secret values were generated on this server and are not displayed."
echo "Settings now present, with secrets hidden:"
sed -E 's/^((POSTGRES_PASSWORD|SECRET_KEY|REDIS_PASSWORD|INFERENCE_API_KEY)=).*/\1<hidden>/' "$target" \
  | grep -Ev '^(#|$)'

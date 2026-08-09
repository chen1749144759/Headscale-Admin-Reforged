#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
headscale_dir=${HEADSCALE_SOURCE:-"$repo_dir/../Headscale-Admin-AE"}
push_images=false
save_dir=""

usage() {
  cat >&2 <<'EOF'
Usage: ./docker/build-account-images.sh [--push] [--save DIRECTORY]

Builds pinned Headscale-Admin-AE, ScaleForge backend and ScaleForge nginx images.
EOF
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --push) push_images=true; shift ;;
    --save)
      [ "$#" -ge 2 ] || usage
      save_dir=$2
      shift 2
      ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

command -v docker >/dev/null 2>&1 || { echo "docker is not installed" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "docker daemon is not available" >&2; exit 1; }
[ -f "$headscale_dir/Dockerfile" ] || { echo "Headscale source not found: $headscale_dir" >&2; exit 1; }

date_tag=$(date -u +%Y%m%d)
scaleforge_commit=$(git -C "$repo_dir" rev-parse --short=8 HEAD)
headscale_commit=$(git -C "$headscale_dir" rev-parse --short=8 HEAD)
scaleforge_tag="$date_tag-$scaleforge_commit"
headscale_tag="$date_tag-$headscale_commit"

backend_image="chenzeshi/scaleforge-backend:$scaleforge_tag"
nginx_image="chenzeshi/scaleforge-nginx:$scaleforge_tag"
headscale_image="chenzeshi/headscale-admin-ae:$headscale_tag"

docker build --pull \
  -f "$repo_dir/docker/backend/Dockerfile" \
  -t "$backend_image" \
  -t chenzeshi/scaleforge-backend:latest \
  "$repo_dir"
docker build --pull \
  -f "$repo_dir/docker/nginx/Dockerfile" \
  -t "$nginx_image" \
  -t chenzeshi/scaleforge-nginx:latest \
  "$repo_dir"
docker build --pull \
  --build-arg "VERSION=$headscale_tag" \
  -f "$headscale_dir/Dockerfile" \
  -t "$headscale_image" \
  -t chenzeshi/headscale-admin-ae:latest \
  "$headscale_dir"

if [ "$push_images" = true ]; then
  for image in \
    "$backend_image" chenzeshi/scaleforge-backend:latest \
    "$nginx_image" chenzeshi/scaleforge-nginx:latest \
    "$headscale_image" chenzeshi/headscale-admin-ae:latest; do
    docker push "$image"
  done
fi

if [ -n "$save_dir" ]; then
  mkdir -p "$save_dir"
  archive="$save_dir/scaleforge-account-stack-$date_tag.tar"
  docker save -o "$archive" "$backend_image" "$nginx_image" "$headscale_image"
  sha256sum "$archive" > "$archive.sha256"
  echo "Saved image bundle: $archive"
fi

cat <<EOF
Pin these values in docker/.env:
AE_VERSION=$headscale_tag
BACKEND_VERSION=$scaleforge_tag
NGINX_VERSION=$scaleforge_tag
EOF

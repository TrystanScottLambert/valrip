#!/bin/bash
set -euo pipefail

# Check for version bump argument
BUMP_TYPE=${1:-patch} # Default to patch if no argument provided

if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
  echo "Error: Invalid bump type. Use 'major', 'minor', or 'patch'"
  echo "Usage: $0 [major|minor|patch]"
  exit 1
fi

# In-place sed that works on both GNU (Linux) and BSD (macOS) without leaving .bak files
sed_inplace() {
  if sed --version >/dev/null 2>&1; then
    sed -E -i "$@"
  else
    sed -E -i '' "$@"
  fi
}

# Always clean up the cloned repos, even if something fails
WORKDIR=$(pwd)
cleanup() {
  cd "$WORKDIR"
  rm -rf rip-validator/ valrip/
}
trap cleanup EXIT

# Clone repositories
git clone git@dev.aao.org.au:waves/twg6/rip-validator.git
git clone git@github.com:TrystanScottLambert/valrip.git

# Copy files
cp -r rip-validator/rip_validator valrip/
cp rip-validator/pyproject.toml valrip/

cd valrip

# Get latest tag and parse version
LATEST_TAG=$(git tag | sort -V | tail -n 1) # e.g., v0.0.6
LATEST_TAG=${LATEST_TAG:-v0.0.0}            # Handle a repo with no tags yet
IFS='.' read -r MAJOR MINOR PATCH <<<"${LATEST_TAG#v}"

# Bump version based on type
case $BUMP_TYPE in
major)
  MAJOR=$((MAJOR + 1))
  MINOR=0
  PATCH=0
  ;;
minor)
  MINOR=$((MINOR + 1))
  PATCH=0
  ;;
patch)
  PATCH=$((PATCH + 1))
  ;;
esac

NEW_TAG="v${MAJOR}.${MINOR}.${PATCH}"
NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}" # Version without 'v' prefix

# Update README.md to use the new release tag
sed_inplace "s#(releases/download/)v[0-9]+\.[0-9]+\.[0-9]+#\1$NEW_TAG#g" README.md

# Update pyproject.toml version field
sed_inplace "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Update __version__ in the package (this is what the compiled executable reports)
INIT_FILE="rip_validator/__init__.py"
sed_inplace "s/^__version__ = [\"'].*[\"']/__version__ = \"$NEW_VERSION\"/" "$INIT_FILE"

# Fail loudly if either version update didn't take
grep -q "^version = \"$NEW_VERSION\"" pyproject.toml || {
  echo "Error: failed to update version in pyproject.toml"
  exit 1
}
grep -q "^__version__ = \"$NEW_VERSION\"" "$INIT_FILE" || {
  echo "Error: failed to update __version__ in $INIT_FILE"
  exit 1
}

# Commit changes
git add .
git commit -m "Deploying $NEW_TAG"
git push

# Create and push new tag
git tag "$NEW_TAG"
git push origin "$NEW_TAG"

echo "Deployed with new tag: $NEW_TAG (bumped $BUMP_TYPE version)"

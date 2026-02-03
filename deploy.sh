#!/bin/bash

# Check for version bump argument
BUMP_TYPE=${1:-patch}  # Default to patch if no argument provided

if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
  echo "Error: Invalid bump type. Use 'major', 'minor', or 'patch'"
  echo "Usage: $0 [major|minor|patch]"
  exit 1
fi

# Clone repositories
git clone git@dev.aao.org.au:waves/twg6/rip-validator.git
git clone git@github.com:TrystanScottLambert/valrip.git

# Copy files
cp -r rip-validator/rip_validator valrip/
cp rip-validator/requirements.txt valrip/
cp rip-validator/pyproject.toml valrip/
cp rip-validator/valrip.spec valrip/

cd valrip

# Get latest tag and parse version
LATEST_TAG=$(git tag | sort -V | tail -n 1) # e.g., v0.0.6
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
if sed --version >/dev/null 2>&1; then
  sed -E -i.bak "s#(releases/download/)v[0-9]+\.[0-9]+\.[0-9]+#\1$NEW_TAG#g" README.md
else
  sed -E -i '' "s#(releases/download/)v[0-9]+\.[0-9]+\.[0-9]+#\1$NEW_TAG#g" README.md
fi

# Update pyproject.toml version field
if sed --version >/dev/null 2>&1; then
  sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
  sed -i '' "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Commit changes
git add .
git commit -m "Deploying $NEW_TAG"
git push

# Create and push new tag
git tag $NEW_TAG
git push origin $NEW_TAG

cd ..
rm -rf rip-validator/
rm -rf valrip/

echo "Deployed with new tag: $NEW_TAG (bumped $BUMP_TYPE version)"

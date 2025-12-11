#!/bin/bash

# Clone repositories
git clone git@dev.aao.org.au:waves/twg6/rip-validator.git
git clone git@github.com:TrystanScottLambert/valrip.git

# Copy files
cp -r rip-validator/rip_validator valrip/
cp rip-validator/requirements.txt valrip/
cp rip-validator/pyproject.toml valrip/
cp rip-validator/valrip.spec valrip/

cd valrip

# Auto-increment patch version
LATEST_TAG=$(git tag | sort -V | tail -n 1) # e.g., v0.0.6
IFS='.' read -r MAJOR MINOR PATCH <<<"${LATEST_TAG#v}"
PATCH=$((PATCH + 1))
NEW_TAG="v${MAJOR}.${MINOR}.${PATCH}"

# Update README.md to use the new release tag
if sed --version >/dev/null 2>&1; then
  sed -E -i.bak "s#(releases/download/)v[0-9]+\.[0-9]+\.[0-9]+#\1$NEW_TAG#g" README.md
else
  sed -E -i '' "s#(releases/download/)v[0-9]+\.[0-9]+\.[0-9]+#\1$NEW_TAG#g" README.md
fi

# Commit changes
git add .
git commit -m "Deploying"
git push

# Create and push new tag
git tag $NEW_TAG
git push origin $NEW_TAG
cd ..
rm -rf rip-validator/
rm -rf valrip/

echo "Deployed with new tag: $NEW_TAG"

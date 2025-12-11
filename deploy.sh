#!/bin/bash

# Clone repositories
git clone git@dev.aao.org.au:waves/twg6/rip-validator.git
git clone git@github.com:TrystanScottLambert/testing_deployment.git

# Copy files
cp -r rip-validator/rip-validator/ testing_deployment/
cp rip-validator/requirements.txt testing_deployment/
cp rip-validator/pyproject.toml testing_deployment/
cp rip-validator/valrip.spec testing_deployment/

cd testing_deployment

# Commit changes
git add .
git commit -m "Deploying"
git push

# Auto-increment patch version
LATEST_TAG=$(git tag | sort -V | tail -n 1) # e.g., v0.0.6
IFS='.' read -r MAJOR MINOR PATCH <<<"${LATEST_TAG#v}"
PATCH=$((PATCH + 1))
NEW_TAG="v${MAJOR}.${MINOR}.${PATCH}"

# Create and push new tag
git tag $NEW_TAG
git push origin $NEW_TAG

echo "Deployed with new tag: $NEW_TAG"

rm -rf rip-validator/
rm -rf testing_deployment/

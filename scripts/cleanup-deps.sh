#!/bin/bash

# Cleanup Script - Remove unused dependencies
# This script removes Python packages that are no longer needed

echo "🧹 Cleaning up unused dependencies..."

# List of packages to remove (packages that were in requirements but not actually used)
UNUSED_PACKAGES=(
    "authlib"
)

# Note: backoff is actually used in the code, so we keep it

# Check if packages are installed and remove them
for package in "${UNUSED_PACKAGES[@]}"; do
    if pip3 show "$package" &> /dev/null; then
        echo "📦 Removing unused package: $package"
        pip3 uninstall -y "$package"
    else
        echo "ℹ️  Package $package is not installed"
    fi
done

# Show remaining packages related to the project
echo ""
echo "📋 Remaining project dependencies:"
echo "-----------------------------------"
pip3 show oauthlib httpx websockets 2>/dev/null || echo "Some packages may not be installed yet"

echo ""
echo "✅ Cleanup completed!"
echo "💡 To install the required dependencies, run:"
echo "   pip3 install oauthlib==3.2.2 httpx>=0.24.0 websockets backoff>=2.0.0"
#!/bin/bash

# Release Script for Gardena Smart System v1.0.3
# This script will commit changes, create a tag, and push to repository

set -e

echo "🚀 Starting release process for Gardena Smart System v1.0.3"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Stage all changes
echo "📦 Staging changes..."
git add .

# Commit with the release message
echo "💾 Committing changes..."
git commit -m "Release v1.0.3 - Complete Gardena Smart System Integration

- Complete implementation of Gardena Smart System integration
- Full device support: mowers, water control, irrigation, power sockets
- Real-time duration tracking and monitoring
- WebSocket communication for live updates
- Multi-language support (EN, DE, FR, NL, FI, SK, SV, NB)
- OAuth2 authentication with token management
- Comprehensive error handling and logging
- HACS integration ready
- Supports all European Gardena Smart System regions"

# Create a git tag for the release
echo "🏷️  Creating git tag v1.0.3..."
git tag -a v1.0.3 -m "Release v1.0.3 - Complete Gardena Smart System Integration"

# Push changes and tags to remote
echo "🌐 Pushing to remote repository..."
git push origin main
git push origin v1.0.3

echo "✅ Release v1.0.3 completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Go to GitHub repository: https://github.com/thecem/gardena-smart-system"
echo "2. Create a new release from the v1.0.3 tag"
echo "3. Use the content from RELEASE_NOTES_v1.0.3.md as release description"
echo "4. Update HACS if needed"
echo ""
echo "🎉 Release v1.0.3 is ready!"
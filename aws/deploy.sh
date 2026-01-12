#!/bin/bash
# Evenflow MCP Server - Deployment Script
# Usage: ./deploy.sh [dev|staging|prod]

set -e

ENVIRONMENT=${1:-dev}

echo "🚀 Deploying Evenflow MCP Server to $ENVIRONMENT..."

# Check prerequisites
if ! command -v sam &> /dev/null; then
    echo "❌ AWS SAM CLI not found. Install with: pip install aws-sam-cli"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install with: pip install awscli"
    exit 1
fi

# Verify AWS credentials
echo "🔑 Verifying AWS credentials..."
aws sts get-caller-identity > /dev/null || {
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
}

# Change to aws directory
cd "$(dirname "$0")"

# Copy required files
echo "📦 Packaging application..."
rm -rf .aws-sam/build 2>/dev/null || true

# Copy MCP and world modules for Lambda
mkdir -p package
cp -r ../mcp package/
cp -r ../world package/
cp lambda_handler.py package/

# Install dependencies
pip install -q -t package -r requirements-lambda.txt

# Build with SAM
echo "🔨 Building SAM application..."
sam build --use-container=false

# Deploy
echo "☁️ Deploying to AWS..."
sam deploy \
    --config-env "$ENVIRONMENT" \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset

# Get outputs
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "evenflow-mcp-$ENVIRONMENT" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Cleanup
rm -rf package

echo ""
echo "🎉 Done! Your MCP server is live."

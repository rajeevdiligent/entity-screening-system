#!/bin/bash

# Production Secrets Setup Script
# This script sets up AWS Secrets Manager and Parameter Store for production deployment

set -e

echo "🔐 Setting up production secrets and parameters..."

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${ENVIRONMENT:-production}
PROJECT_NAME="search-agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS CLI is not configured or credentials are invalid"
    exit 1
fi

print_status "AWS CLI configured successfully"

# Function to create secret if it doesn't exist
create_secret_if_not_exists() {
    local secret_name=$1
    local secret_description=$2
    
    if aws secretsmanager describe-secret --secret-id "$secret_name" --region "$AWS_REGION" > /dev/null 2>&1; then
        print_warning "Secret $secret_name already exists, skipping creation"
    else
        print_status "Creating secret: $secret_name"
        aws secretsmanager create-secret \
            --name "$secret_name" \
            --description "$secret_description" \
            --region "$AWS_REGION" \
            --tags '[
                {"Key": "Environment", "Value": "'$ENVIRONMENT'"},
                {"Key": "Project", "Value": "'$PROJECT_NAME'"},
                {"Key": "ManagedBy", "Value": "setup-script"}
            ]'
        print_status "Secret $secret_name created successfully"
    fi
}

# Function to create parameter if it doesn't exist
create_parameter_if_not_exists() {
    local parameter_name=$1
    local parameter_value=$2
    local parameter_type=$3
    local parameter_description=$4
    
    if aws ssm get-parameter --name "$parameter_name" --region "$AWS_REGION" > /dev/null 2>&1; then
        print_warning "Parameter $parameter_name already exists, skipping creation"
    else
        print_status "Creating parameter: $parameter_name"
        aws ssm put-parameter \
            --name "$parameter_name" \
            --value "$parameter_value" \
            --type "$parameter_type" \
            --description "$parameter_description" \
            --region "$AWS_REGION" \
            --tags '[
                {"Key": "Environment", "Value": "'$ENVIRONMENT'"},
                {"Key": "Project", "Value": "'$PROJECT_NAME'"},
                {"Key": "ManagedBy", "Value": "setup-script"}
            ]'
        print_status "Parameter $parameter_name created successfully"
    fi
}

# Create secrets in AWS Secrets Manager
print_status "Creating secrets in AWS Secrets Manager..."

create_secret_if_not_exists \
    "serper-api-key" \
    "Serper API key for search functionality"

create_secret_if_not_exists \
    "github-token" \
    "GitHub personal access token for repository operations"

# Create parameters in AWS Systems Manager Parameter Store
print_status "Creating parameters in AWS Systems Manager Parameter Store..."

create_parameter_if_not_exists \
    "/$PROJECT_NAME/$ENVIRONMENT/dynamodb/table-name" \
    "search-analysis-results" \
    "String" \
    "DynamoDB table name for storing search results"

create_parameter_if_not_exists \
    "/$PROJECT_NAME/$ENVIRONMENT/lambda/timeout" \
    "60" \
    "String" \
    "Default timeout for Lambda functions in seconds"

create_parameter_if_not_exists \
    "/$PROJECT_NAME/$ENVIRONMENT/lambda/memory-size" \
    "512" \
    "String" \
    "Default memory size for Lambda functions in MB"

create_parameter_if_not_exists \
    "/$PROJECT_NAME/$ENVIRONMENT/api/rate-limit" \
    "100" \
    "String" \
    "API rate limit per minute per client"

create_parameter_if_not_exists \
    "/$PROJECT_NAME/$ENVIRONMENT/monitoring/namespace" \
    "SearchAgent" \
    "String" \
    "CloudWatch metrics namespace"

# Instructions for manual secret value updates
print_status "Secrets and parameters created successfully!"
echo ""
print_warning "IMPORTANT: You need to manually update the secret values:"
echo ""
echo "1. Update Serper API key:"
echo "   aws secretsmanager update-secret --secret-id serper-api-key --secret-string 'YOUR_ACTUAL_API_KEY' --region $AWS_REGION"
echo ""
echo "2. Update GitHub token:"
echo "   aws secretsmanager update-secret --secret-id github-token --secret-string 'YOUR_GITHUB_TOKEN' --region $AWS_REGION"
echo ""

# Create IAM policy for Lambda functions to access secrets
print_status "Creating IAM policy for Lambda functions..."

POLICY_DOCUMENT='{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "arn:aws:secretsmanager:'$AWS_REGION':*:secret:serper-api-key*",
                "arn:aws:secretsmanager:'$AWS_REGION':*:secret:github-token*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": [
                "arn:aws:ssm:'$AWS_REGION':*:parameter/'$PROJECT_NAME'/'$ENVIRONMENT'/*"
            ]
        }
    ]
}'

POLICY_NAME="${PROJECT_NAME}-${ENVIRONMENT}-secrets-policy"

if aws iam get-policy --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$POLICY_NAME" > /dev/null 2>&1; then
    print_warning "IAM policy $POLICY_NAME already exists, updating..."
    aws iam create-policy-version \
        --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$POLICY_NAME" \
        --policy-document "$POLICY_DOCUMENT" \
        --set-as-default
else
    print_status "Creating IAM policy: $POLICY_NAME"
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document "$POLICY_DOCUMENT" \
        --description "Policy for $PROJECT_NAME Lambda functions to access secrets and parameters"
fi

print_status "IAM policy created/updated successfully"

# Create CloudWatch Log Groups
print_status "Creating CloudWatch Log Groups..."

LOG_GROUPS=(
    "/aws/lambda/search-service"
    "/aws/lambda/llm-analysis-service"
    "/aws/lambda/search-results-service"
    "/aws/lambda/orchestrator-function"
)

for log_group in "${LOG_GROUPS[@]}"; do
    if aws logs describe-log-groups --log-group-name-prefix "$log_group" --region "$AWS_REGION" | grep -q "$log_group"; then
        print_warning "Log group $log_group already exists, skipping"
    else
        print_status "Creating log group: $log_group"
        aws logs create-log-group \
            --log-group-name "$log_group" \
            --region "$AWS_REGION"
        
        # Set retention policy (30 days for production)
        aws logs put-retention-policy \
            --log-group-name "$log_group" \
            --retention-in-days 30 \
            --region "$AWS_REGION"
    fi
done

# Create SNS topic for alerts
print_status "Creating SNS topic for alerts..."

ALERT_TOPIC_NAME="${PROJECT_NAME}-${ENVIRONMENT}-alerts"

if aws sns get-topic-attributes --topic-arn "arn:aws:sns:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):$ALERT_TOPIC_NAME" > /dev/null 2>&1; then
    print_warning "SNS topic $ALERT_TOPIC_NAME already exists, skipping"
else
    print_status "Creating SNS topic: $ALERT_TOPIC_NAME"
    TOPIC_ARN=$(aws sns create-topic \
        --name "$ALERT_TOPIC_NAME" \
        --region "$AWS_REGION" \
        --query 'TopicArn' \
        --output text)
    
    print_status "SNS topic created: $TOPIC_ARN"
    
    # Add tags to the topic
    aws sns tag-resource \
        --resource-arn "$TOPIC_ARN" \
        --tags '[
            {"Key": "Environment", "Value": "'$ENVIRONMENT'"},
            {"Key": "Project", "Value": "'$PROJECT_NAME'"},
            {"Key": "Purpose", "Value": "alerts"}
        ]'
fi

print_status "✅ Production secrets and infrastructure setup completed!"
echo ""
print_status "Next steps:"
echo "1. Update the secret values with your actual API keys"
echo "2. Subscribe to the SNS alerts topic for notifications"
echo "3. Deploy your CloudFormation stack"
echo "4. Run the production deployment pipeline"
echo ""
print_status "Setup script completed successfully! 🚀"

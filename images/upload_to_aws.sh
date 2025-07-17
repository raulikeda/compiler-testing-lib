#!/bin/bash
set -e

# Variables (edit as needed)
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_PREFIX=compiler-testing-lib

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

for dir in */ ; do
    if [ -f "$dir/Dockerfile" ]; then
        LANG=${dir%/}
        IMAGE_NAME="$REPO_PREFIX-$LANG:latest"
        ECR_REPO="$REPO_PREFIX-$LANG"
        ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO"

        # Create ECR repo if it doesn't exist
        aws ecr describe-repositories --repository-names $ECR_REPO --region $AWS_REGION || \
            aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION

        # Tag and push
        docker tag $IMAGE_NAME $ECR_URI:latest
        docker push $ECR_URI:latest

        # (Optional) Update ECS service and Lambda function here
        # Placeholder: You must customize the ECS/Lambda update commands for your environment
        echo "Pushed $ECR_URI:latest. Update your ECS service and Lambda as needed."
    fi
done

# Example Lambda update (customize as needed):
# aws lambda update-function-code --function-name <YourLambdaName> --image-uri $ECR_URI:latest --region $AWS_REGION 
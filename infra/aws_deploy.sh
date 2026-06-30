#!/usr/bin/env bash
# =============================================================================
# Swarm64 DA PostgreSQL Deployment — AWS EC2 via Marketplace AMI
# ItalyWorld R&D / Cesare Semovigo — Gotham v3 Bridge
# Reference: https://www.youtube.com/watch?v=pP22EY9nP5E
#
# Prerequisites:
#   aws CLI configured (aws configure)
#   IAM role with ec2:RunInstances, marketplace:Subscribe
#   SSH key pair already created in target region
#
# Usage:
#   chmod +x infra/aws_deploy.sh
#   AWS_REGION=eu-west-1 KEY_PAIR=my-keypair ./infra/aws_deploy.sh
# =============================================================================

set -euo pipefail

# ---- Configuration ----------------------------------------------------------
AWS_REGION="${AWS_REGION:-eu-west-1}"
INSTANCE_TYPE="r5d.12xlarge"         # Swarm64 DA recommended; 96 vCPU, 384 GB RAM, 2x900GB NVMe
KEY_PAIR="${KEY_PAIR:-swarm64-key}"
SECURITY_GROUP="${SECURITY_GROUP:-sg-swarm64-memorydata}"
SUBNET_ID="${SUBNET_ID:-}"           # leave empty for default VPC
EBS_SIZE_GB=500                      # root EBS for pg data dir
EBS_MOUNT="/dev/sdb"                 # Swarm64 DA REQUIRES /dev/sdb
TAG_NAME="memorydata-swarm64-$(date +%Y%m%d)"

# Swarm64 DA 4.0 AMI (eu-west-1; update for other regions from AWS Marketplace)
# Marketplace product: https://aws.amazon.com/marketplace/seller-profile?id=8522da7d-9063-4c81-a09d-005d95fb6930
SWARM64_AMI="${SWARM64_AMI:-ami-PLACEHOLDER}"   # replace with actual AMI ID from Marketplace subscription

# ---- Security Group ---------------------------------------------------------
echo "[1/4] Ensuring security group $SECURITY_GROUP ..."
aws ec2 describe-security-groups \
    --group-names "$SECURITY_GROUP" \
    --region "$AWS_REGION" > /dev/null 2>&1 || \
aws ec2 create-security-group \
    --group-name "$SECURITY_GROUP" \
    --description "Swarm64 MemoryData benchmark cluster" \
    --region "$AWS_REGION"

# Allow SSH from current public IP only
MY_IP=$(curl -s https://checkip.amazonaws.com)/32
aws ec2 authorize-security-group-ingress \
    --group-name "$SECURITY_GROUP" \
    --protocol tcp --port 22 --cidr "$MY_IP" \
    --region "$AWS_REGION" 2>/dev/null || true

# Allow PostgreSQL from same VPC
aws ec2 authorize-security-group-ingress \
    --group-name "$SECURITY_GROUP" \
    --protocol tcp --port 5432 --source-group "$SECURITY_GROUP" \
    --region "$AWS_REGION" 2>/dev/null || true

# ---- Launch Instance --------------------------------------------------------
echo "[2/4] Launching $INSTANCE_TYPE with Swarm64 DA AMI ..."
LAUNCH_ARGS=(
    --image-id "$SWARM64_AMI"
    --instance-type "$INSTANCE_TYPE"
    --key-name "$KEY_PAIR"
    --security-groups "$SECURITY_GROUP"
    --region "$AWS_REGION"
    --block-device-mappings "[
        {
            \"DeviceName\": \"/dev/sda1\",
            \"Ebs\": {\"VolumeSize\": 100, \"VolumeType\": \"gp3\"}
        },
        {
            \"DeviceName\": \"/dev/sdb\",
            \"Ebs\": {\"VolumeSize\": $EBS_SIZE_GB, \"VolumeType\": \"gp3\"}
        }
    ]"
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME},{Key=Project,Value=MemoryData-Swarm64}]"
    --count 1
)

[ -n "$SUBNET_ID" ] && LAUNCH_ARGS+=(--subnet-id "$SUBNET_ID")

INSTANCE_ID=$(aws ec2 run-instances "${LAUNCH_ARGS[@]}" \
    --query 'Instances[0].InstanceId' --output text)

echo "   Instance ID: $INSTANCE_ID"

# ---- Wait for Running -------------------------------------------------------
echo "[3/4] Waiting for instance to reach 'running' state ..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"

PUBLIC_DNS=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicDnsName' \
    --output text --region "$AWS_REGION")

echo "   Public DNS: $PUBLIC_DNS"

# ---- Post-Init: Install pgvector + configure MemoryData ---------------------
echo "[4/4] Bootstrapping PostgreSQL + pgvector + MemoryData schema ..."
ssh -o StrictHostKeyChecking=no -i "${KEY_PAIR}.pem" ubuntu@"$PUBLIC_DNS" << 'REMOTE'
    set -e
    # Install pgvector
    sudo apt-get update -qq
    sudo apt-get install -y postgresql-16-pgvector
    # Clone fork
    git clone https://github.com/Outropy23/MemoryData.git ~/MemoryData
    cd ~/MemoryData
    pip install -r requirements.txt opentelemetry-sdk opentelemetry-api \
        opentelemetry-exporter-otlp psycopg2-binary pgvector numpy
    # Create DB + schema
    sudo -u postgres psql -c "CREATE USER adam_agent WITH PASSWORD 'changeme_in_prod';"
    sudo -u postgres psql -c "CREATE DATABASE memorydata_swarm64 OWNER adam_agent;"
    sudo -u postgres psql -d memorydata_swarm64 -c "CREATE EXTENSION IF NOT EXISTS vector;"
    sudo -u postgres psql -d memorydata_swarm64 -c "CREATE EXTENSION IF NOT EXISTS swarm64da;"
    echo "Bootstrap complete. Run: python evaluation/run_swarm64_benchmark.py"
REMOTE

echo ""
echo "===================================================================="
echo " Swarm64 DA PostgreSQL instance ready."
echo " SSH: ssh -i ${KEY_PAIR}.pem ubuntu@${PUBLIC_DNS}"
echo " DB:  psql -h ${PUBLIC_DNS} -U adam_agent -d memorydata_swarm64"
echo "===================================================================="

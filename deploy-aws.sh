#!/bin/bash
# AWS Deployment Script for Evenflow MUD Server
# Deploys to AWS Lightsail (cheapest option) or EC2

set -e

# Configuration
PROJECT_NAME="evenflow-mud"
REGION="${AWS_REGION:-us-east-1}"

echo "================================================"
echo "Evenflow MUD Server - AWS Deployment"
echo "================================================"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install with: pip install awscli"
    exit 1
fi

# Check if logged in
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ Not logged into AWS. Run: aws configure"
    exit 1
fi

echo "✓ AWS CLI configured"
echo "  Account: $(aws sts get-caller-identity --query 'Account' --output text)"
echo "  Region: $REGION"
echo ""

# Menu
echo "Select deployment option:"
echo ""
echo "1) AWS Lightsail (RECOMMENDED - \$3.50/month)"
echo "   - 512MB RAM, 1 vCPU, 20GB SSD"
echo "   - Fixed monthly cost, no surprises"
echo "   - Includes static IP"
echo ""
echo "2) AWS Lightsail (\$5/month)"  
echo "   - 1GB RAM, 1 vCPU, 40GB SSD"
echo "   - Better for more players"
echo ""
echo "3) EC2 t3.micro (Free Tier eligible, then ~\$8/month)"
echo "   - 1GB RAM, 2 vCPU"
echo "   - 12 months free tier if new account"
echo ""
echo "4) Show cost comparison only"
echo ""

read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        BUNDLE_ID="nano_3_0"
        MONTHLY_COST="3.50"
        ;;
    2)
        BUNDLE_ID="micro_3_0"
        MONTHLY_COST="5.00"
        ;;
    3)
        echo "EC2 deployment - creating CloudFormation stack..."
        deploy_ec2
        exit 0
        ;;
    4)
        show_cost_comparison
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Deploying Lightsail instance ($BUNDLE_ID @ \$$MONTHLY_COST/month)..."
echo ""

# Create Lightsail instance
INSTANCE_NAME="${PROJECT_NAME}-server"

# Check if instance exists
if aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" &> /dev/null; then
    echo "Instance '$INSTANCE_NAME' already exists"
    read -p "Delete and recreate? [y/N]: " confirm
    if [[ $confirm == [yY] ]]; then
        aws lightsail delete-instance --instance-name "$INSTANCE_NAME" --region "$REGION"
        echo "Waiting for deletion..."
        sleep 30
    else
        exit 0
    fi
fi

# Create user data script
USER_DATA=$(cat << 'USERDATA'
#!/bin/bash
set -e

# Update system
apt-get update && apt-get upgrade -y

# Install dependencies
apt-get install -y python3 python3-pip python3-venv git

# Create evenflow user
useradd -m -s /bin/bash evenflow || true

# Clone and setup
cd /home/evenflow
sudo -u evenflow git clone https://github.com/ssergorp/evenflow.git || true
cd evenflow

# Create venv and install
sudo -u evenflow python3 -m venv .venv
sudo -u evenflow .venv/bin/pip install evennia mcp httpx anyio pydantic PyYAML

# Initialize Evennia game
cd /home/evenflow
sudo -u evenflow /home/evenflow/evenflow/.venv/bin/evennia --init evenflow_game || true
cd evenflow_game

# Run migrations
sudo -u evenflow /home/evenflow/evenflow/.venv/bin/evennia migrate

# Configure for external access
cat >> /home/evenflow/evenflow_game/server/conf/settings.py << 'SETTINGS'
ALLOWED_HOSTS = ["*"]
WEBSERVER_INTERFACES = ["0.0.0.0"]
WEBSOCKET_CLIENT_INTERFACE = "0.0.0.0"
DEBUG = False
WEBCLIENT_ENABLED = True
SETTINGS

# Create systemd service
cat > /etc/systemd/system/evenflow.service << 'SERVICE'
[Unit]
Description=Evenflow MUD Server
After=network.target

[Service]
Type=forking
User=evenflow
WorkingDirectory=/home/evenflow/evenflow_game
ExecStart=/home/evenflow/evenflow/.venv/bin/evennia start
ExecStop=/home/evenflow/evenflow/.venv/bin/evennia stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable evenflow
systemctl start evenflow

echo "Evenflow MUD Server installed successfully!"
USERDATA
)

# Create instance
echo "Creating Lightsail instance..."
aws lightsail create-instances \
    --instance-names "$INSTANCE_NAME" \
    --availability-zone "${REGION}a" \
    --blueprint-id "ubuntu_22_04" \
    --bundle-id "$BUNDLE_ID" \
    --user-data "$USER_DATA" \
    --region "$REGION"

echo "✓ Instance created"

# Wait for instance to be running
echo "Waiting for instance to start..."
sleep 60

# Allocate static IP
STATIC_IP_NAME="${PROJECT_NAME}-ip"
echo "Creating static IP..."
aws lightsail allocate-static-ip \
    --static-ip-name "$STATIC_IP_NAME" \
    --region "$REGION" 2>/dev/null || true

aws lightsail attach-static-ip \
    --static-ip-name "$STATIC_IP_NAME" \
    --instance-name "$INSTANCE_NAME" \
    --region "$REGION"

# Open firewall ports
echo "Configuring firewall..."
aws lightsail open-instance-public-ports \
    --instance-name "$INSTANCE_NAME" \
    --port-info fromPort=4000,toPort=4000,protocol=tcp \
    --region "$REGION"

aws lightsail open-instance-public-ports \
    --instance-name "$INSTANCE_NAME" \
    --port-info fromPort=4001,toPort=4001,protocol=tcp \
    --region "$REGION"

aws lightsail open-instance-public-ports \
    --instance-name "$INSTANCE_NAME" \
    --port-info fromPort=4002,toPort=4002,protocol=tcp \
    --region "$REGION"

# Get IP
IP=$(aws lightsail get-static-ip --static-ip-name "$STATIC_IP_NAME" --region "$REGION" --query 'staticIp.ipAddress' --output text)

echo ""
echo "================================================"
echo "✓ Deployment Complete!"
echo "================================================"
echo ""
echo "Instance: $INSTANCE_NAME"
echo "IP Address: $IP"
echo "Monthly Cost: \$$MONTHLY_COST"
echo ""
echo "Access your MUD:"
echo "  Web Client: http://$IP:4001"
echo "  Telnet:     telnet $IP 4000"
echo "  Websocket:  ws://$IP:4002"
echo ""
echo "SSH Access:"
echo "  Download key from Lightsail console"
echo "  ssh -i LightsailDefaultKey.pem ubuntu@$IP"
echo ""
echo "Note: Server needs ~5 minutes to fully initialize"
echo ""

show_cost_comparison() {
    echo ""
    echo "================================================"
    echo "AWS Cost Comparison for MUD Hosting"
    echo "================================================"
    echo ""
    echo "Option 1: Lightsail Nano (CHEAPEST)"
    echo "  - \$3.50/month fixed"
    echo "  - 512MB RAM, 1 vCPU, 20GB SSD"
    echo "  - Good for 5-10 concurrent players"
    echo "  - Includes 1TB data transfer"
    echo ""
    echo "Option 2: Lightsail Micro"
    echo "  - \$5.00/month fixed"
    echo "  - 1GB RAM, 1 vCPU, 40GB SSD"
    echo "  - Good for 10-25 players"
    echo "  - Includes 2TB data transfer"
    echo ""
    echo "Option 3: EC2 t3.micro"
    echo "  - FREE for 12 months (new accounts)"
    echo "  - Then ~\$8.50/month"
    echo "  - 1GB RAM, 2 vCPU"
    echo "  - Pay for data transfer separately"
    echo ""
    echo "Option 4: EC2 t4g.nano (ARM)"
    echo "  - ~\$3.00/month"
    echo "  - 512MB RAM, 2 vCPU"
    echo "  - Requires ARM-compatible software"
    echo ""
    echo "Recommendation: Lightsail Nano (\$3.50/mo)"
    echo "  Best value, predictable cost, easy to manage"
    echo ""
}

deploy_ec2() {
    echo "Creating EC2 deployment via CloudFormation..."
    
    # Create CloudFormation template
    cat > /tmp/evenflow-ec2.yaml << 'CFTEMPLATE'
AWSTemplateFormatVersion: '2010-09-09'
Description: Evenflow MUD Server on EC2

Parameters:
  InstanceType:
    Type: String
    Default: t3.micro
    AllowedValues:
      - t3.micro
      - t3.small
      - t4g.nano
      - t4g.micro

Resources:
  SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Evenflow MUD ports
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 4000
          ToPort: 4002
          CidrIp: 0.0.0.0/0

  Instance:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: !Ref InstanceType
      ImageId: !Sub '{{resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id}}'
      SecurityGroups:
        - !Ref SecurityGroup
      Tags:
        - Key: Name
          Value: evenflow-mud
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          apt-get update && apt-get install -y python3 python3-pip python3-venv git
          # ... (same user data as Lightsail)

Outputs:
  PublicIP:
    Value: !GetAtt Instance.PublicIp
    Description: Server IP address
CFTEMPLATE

    aws cloudformation create-stack \
        --stack-name evenflow-mud \
        --template-body file:///tmp/evenflow-ec2.yaml \
        --region "$REGION"
    
    echo "Stack creation started. Check CloudFormation console for status."
}

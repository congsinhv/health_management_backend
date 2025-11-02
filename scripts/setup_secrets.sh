#!/bin/bash
# Script to create and verify Secret Manager secrets

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEV_PROJECT="vhealth-dev"
PROD_PROJECT="vhealth-prod"
REGION="asia-southeast1"

echo -e "${YELLOW}=== Secret Manager Setup ===${NC}\n"

# Function to check if secret exists
check_secret() {
    local project=$1
    local secret_name=$2
    
    if gcloud secrets describe ${secret_name} --project=${project} &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to create secret
create_secret() {
    local project=$1
    local secret_name=$2
    local secret_value=$3
    
    echo -e "${YELLOW}Creating secret: ${secret_name}${NC}"
    
    # Create the secret
    echo -n "${secret_value}" | gcloud secrets create ${secret_name} \
        --project=${project} \
        --replication-policy="user-managed" \
        --locations=${REGION} \
        --data-file=-
    
    echo -e "${GREEN}✓ Secret ${secret_name} created${NC}"
}

# Function to update secret
update_secret() {
    local project=$1
    local secret_name=$2
    local secret_value=$3
    
    echo -e "${YELLOW}Updating secret: ${secret_name}${NC}"
    
    # Add new version
    echo -n "${secret_value}" | gcloud secrets versions add ${secret_name} \
        --project=${project} \
        --data-file=-
    
    echo -e "${GREEN}✓ Secret ${secret_name} updated${NC}"
}

# Function to grant access to Cloud Run service account
grant_secret_access() {
    local project=$1
    local secret_name=$2
    local env=$3
    
    local service_account="vhealth-backend-${env}@${project}.iam.gserviceaccount.com"
    
    echo -e "${BLUE}  Granting access to ${service_account}${NC}"
    
    gcloud secrets add-iam-policy-binding ${secret_name} \
        --project=${project} \
        --member="serviceAccount:${service_account}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet
    
    echo -e "${GREEN}  ✓ Access granted${NC}"
}

# Function to setup secrets for an environment
setup_environment_secrets() {
    local project=$1
    local env=$2
    
    echo -e "\n${YELLOW}=== Setting up secrets for ${env} environment ===${NC}\n"
    
    # Set project
    gcloud config set project ${project}
    
    # Define required secrets as parallel arrays (portable across bash/zsh)
    local secret_names=(
        "vhealth-${env}-database-url"
        "vhealth-${env}-secret-key"
        "vhealth-${env}-google-client-id"
        "vhealth-${env}-google-client-secret"
        "vhealth-${env}-mail-username"
        "vhealth-${env}-mail-password"
    )
    
    local secret_descriptions=(
        "PostgreSQL connection string"
        "JWT secret key for token signing"
        "Google OAuth 2.0 client ID"
        "Google OAuth 2.0 client secret"
        "SMTP email username"
        "SMTP email password"
    )
    
    # Check each secret
    local idx=0
    for secret_name in "${secret_names[@]}"; do
        description="${secret_descriptions[$idx]}"
        idx=$((idx + 1))
        
        echo -e "${YELLOW}Checking: ${secret_name}${NC}"
        echo -e "${BLUE}  Description: ${description}${NC}"
        
        if check_secret ${project} ${secret_name}; then
            echo -e "${GREEN}✓ Secret exists${NC}"
            
            # Show last updated
            LAST_UPDATED=$(gcloud secrets versions list ${secret_name} \
                --project=${project} \
                --limit=1 \
                --format="value(createTime)")
            echo -e "${BLUE}  Last updated: ${LAST_UPDATED}${NC}"
            
            # Ensure service account has access
            grant_secret_access ${project} ${secret_name} ${env}
            
            # Ask if user wants to update
            read -p "  Update this secret? (y/N): " update_choice
            if [[ $update_choice =~ ^[Yy]$ ]]; then
                read -sp "  Enter new value: " new_value
                echo ""
                update_secret ${project} ${secret_name} "${new_value}"
            fi
        else
            echo -e "${RED}✗ Secret does NOT exist${NC}"
            
            read -p "  Create this secret? (y/N): " create_choice
            if [[ $create_choice =~ ^[Yy]$ ]]; then
                read -sp "  Enter value: " secret_value
                echo ""
                create_secret ${project} ${secret_name} "${secret_value}"
                grant_secret_access ${project} ${secret_name} ${env}
            else
                echo -e "${YELLOW}  Skipped${NC}"
            fi
        fi
        echo ""
    done
}

# Function to list all secrets for an environment
list_secrets() {
    local project=$1
    local env=$2
    
    echo -e "\n${YELLOW}=== Secrets in ${env} environment ===${NC}\n"
    
    gcloud config set project ${project}
    
    echo -e "${BLUE}Secrets matching 'vhealth-${env}-*':${NC}"
    gcloud secrets list --project=${project} --filter="name:vhealth-${env}" --format="table(name,createTime)"
}

# Main menu
echo -e "${YELLOW}Select operation:${NC}"
echo "1) Setup Dev secrets"
echo "2) Setup Prod secrets"
echo "3) Setup Both"
echo "4) List Dev secrets"
echo "5) List Prod secrets"
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        setup_environment_secrets ${DEV_PROJECT} "dev"
        ;;
    2)
        setup_environment_secrets ${PROD_PROJECT} "prod"
        ;;
    3)
        setup_environment_secrets ${DEV_PROJECT} "dev"
        setup_environment_secrets ${PROD_PROJECT} "prod"
        ;;
    4)
        list_secrets ${DEV_PROJECT} "dev"
        ;;
    5)
        list_secrets ${PROD_PROJECT} "prod"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}=== Setup Complete ===${NC}"
echo -e "\n${YELLOW}Verify secrets:${NC}"
echo "gcloud secrets list --project=${DEV_PROJECT} --filter='name:vhealth-dev'"
echo ""
echo -e "${YELLOW}View secret versions:${NC}"
echo "gcloud secrets versions list vhealth-dev-database-url --project=${DEV_PROJECT}"


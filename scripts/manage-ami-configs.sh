#!/bin/bash

# scripts/manage-workflows.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$REPO_ROOT/workflows"
WORKFLOW_DIR="$REPO_ROOT/.github/workflows"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  sync              Sync all workflows to .github/workflows"
    echo "  create <path>     Create new AMI configuration"
    echo "  validate [path]   Validate configuration files"
    echo "  list              List all configurations"
    echo "  clean             Clean synced workflow files"
    echo ""
    echo "Examples:"
    echo "  $0 sync"
    echo "  $0 create ubuntu/22.04/arm64"
    echo "  $0 validate workflows/ubuntu/20.04/x86_64"
    echo "  $0 list"
}

sync_workflows() {
    echo "Syncing AMI workflow files..."
    
    # 既存の同期済みファイルをクリア
    find "$WORKFLOW_DIR" -name "ami-*.yaml" -delete 2>/dev/null || true
    
    # 新しいファイルをコピー
    find "$CONFIG_DIR" -name "workflow.yaml" -type f | while read -r source_file; do
        # パスから適切なファイル名を生成
        config_path=$(dirname "$source_file" | sed "s|$CONFIG_DIR/||g")
        target_name="ami-$(echo "$config_path" | sed 's|/|-|g').yaml"
        target_path="$WORKFLOW_DIR/$target_name"
        
        echo "Copying $source_file -> $target_path"
        cp "$source_file" "$target_path"
        
        # ワークフローにメタ情報を追加
        {
            echo "# Auto-generated from $source_file"
            echo "# Config path: workflows/$config_path"
            echo "# Last synced: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            echo ""
            cat "$source_file"
        } > "$target_path.tmp"
        
        mv "$target_path.tmp" "$target_path"
    done
    
    echo "Workflow sync completed."
}

create_config() {
    local config_path="$1"
    
    if [ -z "$config_path" ]; then
        echo "Error: Configuration path required"
        echo "Example: ubuntu/20.04/x86_64"
        exit 1
    fi
    
    local full_path="$CONFIG_DIR/$config_path"
    
    if [ -d "$full_path" ]; then
        echo "Error: Configuration already exists at $full_path"
        exit 1
    fi
    
    echo "Creating AMI configuration at $config_path..."
    
    mkdir -p "$full_path"
    
    # Extract OS info from path
    local os_name=$(echo "$config_path" | cut -d'/' -f1)
    local os_version=$(echo "$config_path" | cut -d'/' -f2)
    local architecture=$(echo "$config_path" | cut -d'/' -f3)
    
    # Create workflow.yaml
    cat > "$full_path/workflow.yaml" << EOF
name: Build $os_name $os_version $architecture AMI

on:
  workflow_dispatch:
    inputs:
      config_path:
        description: 'Configuration path'
        required: false
        default: 'workflows/$config_path'
      trigger_reason:
        description: 'Reason for triggering'
        required: false
        default: 'manual'
  push:
    paths:
      - 'workflows/$config_path/**'
  schedule:
    # 毎週日曜日の午前2時 (UTC)
    - cron: '0 2 * * 0'

env:
  CONFIG_PATH: workflows/$config_path
  OS_NAME: $os_name
  OS_VERSION: "$os_version"
  ARCHITECTURE: $architecture

jobs:
  build-ami:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: \${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: \${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: \${{ vars.AWS_REGION || 'us-west-2' }}

      # Add your specific build steps here
EOF

    # Create recipe.yaml
    cat > "$full_path/recipe.yaml" << EOF
name: $os_name-$os_version-$architecture-recipe
description: $os_name $os_version $architecture AMI recipe
version: "1.0.0"

# 親イメージ (適切な値に変更してください)
parentImage: "$os_name-server-${os_version//./-}-lts-$architecture"

# コンポーネント
components:
  - name: "update-linux"
    version: "1.0.0"

# インスタンス設定
instanceConfiguration:
  instanceTypes:
    - "t3.medium"
  systemsManagerAgent: true

# 配布設定
distributionConfiguration:
  regions:
    - "us-west-2"

# タグ
tags:
  Environment: "production"
  OS: "$os_name"
  Version: "$os_version"
  Architecture: "$architecture"
EOF

    echo "Created configuration files:"
    echo "  - $full_path/workflow.yaml"
    echo "  - $full_path/recipe.yaml"
    echo ""
    echo "Please review and customize the generated files before use."
}

validate_configs() {
    local target_path="${1:-$CONFIG_DIR}"
    
    echo "Validating AMI configurations in $target_path..."
    
    local errors=0
    
    find "$target_path" -name "recipe.yaml" -type f | while read -r recipe_file; do
        echo "Validating $recipe_file..."
        
        # YAML構文チェック
        if ! python3 -c "import yaml; yaml.safe_load(open('$recipe_file'))" 2>/dev/null; then
            echo "  Error: Invalid YAML syntax in $recipe_file"
            ((errors++))
            continue
        fi
        
        # 必須フィールドチェック
        if ! grep -q "^name:" "$recipe_file"; then
            echo "  Error: Missing 'name' field in $recipe_file"
            ((errors++))
        fi
        
        if ! grep -q "^parentImage:" "$recipe_file"; then
            echo "  Error: Missing 'parentImage' field in $recipe_file"
            ((errors++))
        fi
        
        echo "  OK: $recipe_file"
    done
    
    # ワークフローファイルの存在チェック
    find "$target_path" -name "recipe.yaml" -type f | while read -r recipe_file; do
        local workflow_file="$(dirname "$recipe_file")/workflow.yaml"
        if [ ! -f "$workflow_file" ]; then
            echo "Error: Missing workflow.yaml for $recipe_file"
            ((errors++))
        fi
    done
    
    if [ $errors -eq 0 ]; then
        echo "All configurations are valid."
    else
        echo "Found $errors validation errors."
        exit 1
    fi
}

list_configs() {
    echo "Available AMI configurations:"
    echo ""
    
    find "$CONFIG_DIR" -name "recipe.yaml" -type f | while read -r recipe_file; do
        local config_path=$(dirname "$recipe_file" | sed "s|$CONFIG_DIR/||g")
        local name=$(grep "^name:" "$recipe_file" | cut -d':' -f2 | tr -d ' ')
        local version=$(grep "^version:" "$recipe_file" | cut -d':' -f2 | tr -d ' "')
        
        echo "  $config_path"
        echo "    Name: $name"
        echo "    Version: $version"
        echo ""
    done
}

clean_workflows() {
    echo "Cleaning synced workflow files..."
    find "$WORKFLOW_DIR" -name "ami-*.yaml" -delete 2>/dev/null || true
    echo "Cleaned workflow files."
}

# メイン処理
case "${1:-}" in
    sync)
        sync_workflows
        ;;
    create)
        create_config "$2"
        ;;
    validate)
        validate_configs "$2"
        ;;
    list)
        list_configs
        ;;
    clean)
        clean_workflows
        ;;
    *)
        usage
        exit 1
        ;;
esac

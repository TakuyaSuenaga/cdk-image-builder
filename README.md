# cdk-image-builder

# AWS Image Builder with CDK セットアップガイド

## 前提条件

1. **AWS アカウント**
   - Image Builder が利用可能なリージョン
   - 適切な IAM 権限

2. **GitHub リポジトリ**
   - GitHub Actions が有効
   - AWS との OIDC 連携設定

## 1. AWS 側の準備

### IAM Role の作成（GitHub Actions 用）

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/YOUR_REPO:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### 必要な IAM ポリシー

GitHub Actions 用ロールに以下のポリシーをアタッチ：

- `AWSImageBuilderFullAccess`
- `AmazonEC2FullAccess`
- `IAMFullAccess`
- `CloudFormationFullAccess`
- `CloudWatchLogsFullAccess`

## 2. リポジトリの準備

### ディレクトリ構造の作成

```bash
mkdir -p image-builder/.github/workflows
mkdir -p image-builder/cdk-deploy
mkdir -p image-builder/my-app/components/component1
mkdir -p image-builder/my-app/components/component2
mkdir -p image-builder/my-app/recipes
```

### ファイルの配置

1. 各 artifact の内容を対応するファイルに保存
2. GitHub Secrets の設定：
   - `AWS_ROLE_ARN`: 作成した IAM Role の ARN

## 3. GitHub Secrets の設定

リポジトリの Settings > Secrets and variables > Actions で以下を設定：

```
AWS_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/GitHubActionsRole
```

## 4. 動作確認

### ローカルでの事前確認

```bash
cd cdk-deploy
pip install -r requirements.txt
export CDK_DEFAULT_REGION=ap-northeast-1
export RECIPE_VERSION=latest

# 構文チェック
python cdk_deploy.py

# CDK Synth
cdk synth
```

### GitHub Actions での実行

1. ファイルをコミット・プッシュ
2. Actions タブで実行状況を確認
3. 成功した場合、AWS Console で Image Builder Pipeline を確認

## 5. カスタマイズ

### 新しいコンポーネントの追加

1. `my-app/components/` に新しいディレクトリを作成
2. バージョンファイル（例：`1.0.0.yaml`）を作成
3. レシピファイルで新しいコンポーネントを参照

### レシピの更新

1. 新しいバージョンファイルを作成（例：`1.2.0.yaml`）
2. 必要に応じてコンポーネントやブロックデバイス設定を更新
3. GitHub Actions で新しいバージョンを指定して実行

## トラブルシューティング

### よくある問題

1. **IAM 権限エラー**
   - GitHub Actions 用ロールの権限を確認
   - Image Builder サービスロールの権限を確認

2. **コンポーネントが見つからない**
   - ファイルパスとファイル名を確認
   - YAML 構文エラーがないか確認

3. **CDK デプロイエラー**
   - リージョンが正しく設定されているか確認
   - CDK Bootstrap が実行されているか確認

### ログの確認

- GitHub Actions のログ
- AWS CloudWatch Logs
- Image Builder Pipeline の実行履歴

## セキュリティ考慮事項

1. **最小権限の原則**
   - 必要最小限の IAM 権限のみ付与
   - リソースレベルでの制限を検討

2. **機密情報の管理**
   - GitHub Secrets の適切な利用
   - ハードコードされた認証情報の禁止

3. **ネットワークセキュリティ**
   - 適切な VPC/サブネット設定
   - セキュリティグループの制限

## 運用のベストプラクティス

1. **バージョン管理**
   - セマンティックバージョニングの遵守
   - 変更履歴の文書化

2. **テスト**
   - ローカルでの事前検証
   - ステージング環境での確認

3. **監視**
   - CloudWatch メトリクスの設定
   - アラートの設定

#  レシピファイル例

```yaml
# ami-configs/ubuntu/20.04/x86_64/recipe.yml
name: ubuntu-20.04-x86_64-recipe
description: Ubuntu 20.04 LTS x86_64 AMI recipe
version: "1.0.0"

# 親イメージ
parentImage: "ubuntu-server-20-lts-x86"

# コンポーネント
components:
  - name: "update-linux"
    version: "1.0.0"
    
  - name: "aws-cli-version-2-linux"
    version: "1.0.0"
    
  - name: "docker-ce-ubuntu"
    version: "1.0.0"
    
  - name: "nodejs-16-linux"
    version: "1.0.0"

# カスタムコンポーネント
customComponents:
  - name: "custom-security-hardening"
    uri: "arn:aws:imagebuilder:us-west-2:123456789012:component/security-hardening/1.0.0"
    
  - name: "custom-monitoring-setup"
    uri: "arn:aws:imagebuilder:us-west-2:123456789012:component/monitoring-setup/1.0.0"

# インスタンス設定
instanceConfiguration:
  instanceTypes:
    - "t3.medium"
  systemsManagerAgent: true
  
# 配布設定
distributionConfiguration:
  regions:
    - "us-west-2"
    - "us-east-1"
  
  # AMI権限
  amiPermissions:
    - accountId: "123456789012"
    - accountId: "987654321098"

# テスト設定
testConfiguration:
  instanceTypes:
    - "t3.small"
  timeoutMinutes: 90
  
# 追加設定
additionalSettings:
  ebsOptimized: true
  enhancedNetworking: true
  sriovNetSupport: "simple"
  
  # ユーザーデータ
  userData: |
    #!/bin/bash
    echo "Starting custom AMI initialization..."
    
    # カスタム設定をここに追加
    systemctl enable docker
    usermod -aG docker ubuntu
    
    echo "AMI initialization completed"

# タグ
tags:
  Environment: "production"
  Team: "infrastructure"
  CostCenter: "engineering"
  Project: "ami-automation"
```

## Personal Access Token の作成手順

GitHubでPATを作成:

GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
"Generate new token (classic)" をクリック
以下の権限を選択:

repo (Full control of private repositories)
workflow (Update GitHub Action workflows)
write:packages (必要に応じて)




リポジトリのSecretsに追加:

リポジトリ → Settings → Secrets and variables → Actions
"New repository secret" をクリック
Name: PAT_TOKEN
Secret: 作成したPATを貼り付け



4. Fine-grained Personal Access Token を使用する場合（推奨）
より安全なFine-grained PATを使用する場合：

Fine-grained PATを作成:

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
"Generate new token" をクリック
Resource owner: 自分のアカウントまたは組織を選択
Repository access: 該当リポジトリを選択
Permissions:

Contents: Read and write
Actions: Write
Metadata: Read
Pull requests: Read

## 推奨する解決策
最も簡単で確実な方法:

Fine-grained Personal Access Token を作成（workflows権限付き）
リポジトリのSecretsに PAT_TOKEN として保存
ワークフローで token: ${{ secrets.PAT_TOKEN }} を使用

この方法により、GitHub Actionsがワークフローファイルを作成・更新できるようになります。
注意点

GITHUB_TOKEN は workflows ディレクトリへの書き込み権限が制限されています
Personal Access Token を使用することで、この制限を回避できます
セキュリティ上、Fine-grained PATの使用を強く推奨します

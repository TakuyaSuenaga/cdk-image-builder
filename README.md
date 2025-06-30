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

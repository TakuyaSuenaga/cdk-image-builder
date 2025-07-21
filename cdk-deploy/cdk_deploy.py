import os
import sys
import yaml
import json
import glob
from pathlib import Path
from typing import Dict, List, Any, Optional
import boto3
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_imagebuilder as imagebuilder,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_logs as logs,
    CfnOutput
)
from constructs import Construct

# boto3で既存リソースのARNを保持するためのヘルパークラス
class ExistingImageBuilderComponent:
    def __init__(self, arn: str):
        self._arn = arn
    
    @property
    def attr_arn(self):
        return self._arn

class ExistingImageBuilderRecipe:
    def __init__(self, arn: str):
        self._arn = arn
    
    @property
    def attr_arn(self):
        return self._arn


class ImageBuilderManager:
    """レシピとコンポーネントファイルの管理クラス"""
    
    def __init__(self, base_path: str = "../my-app"):
        self.base_path = Path(base_path)
        self.components_path = self.base_path / "components"
        self.recipes_path = self.base_path / "recipes"
    
    def get_latest_version(self, versions: List[str]) -> str:
        """バージョンリストから最新バージョンを取得"""
        def version_key(v):
            return tuple(map(int, v.split('.')))
        
        return max(versions, key=version_key)
    
    def get_component_versions(self, component_name: str) -> List[str]:
        """コンポーネントの利用可能バージョンを取得"""
        component_dir = self.components_path / component_name
        if not component_dir.exists():
            return []
        
        versions = []
        for yaml_file in component_dir.glob("*.yaml"):
            version = yaml_file.stem
            versions.append(version)
        
        return versions
    
    def get_recipe_versions(self) -> List[str]:
        """レシピの利用可能バージョンを取得"""
        versions = []
        for yaml_file in self.recipes_path.glob("*.yaml"):
            version = yaml_file.stem
            versions.append(version)
        
        return versions
    
    def load_component(self, component_name: str, version: str = "x.x.x") -> Dict[str, Any]:
        """コンポーネントファイルを読み込み"""
        if version == "x.x.x":
            available_versions = self.get_component_versions(component_name)
            if not available_versions:
                raise ValueError(f"Component {component_name} not found")
            version = self.get_latest_version(available_versions)
        
        component_file = self.components_path / component_name / f"{version}.yaml"
        
        if not component_file.exists():
            raise FileNotFoundError(f"Component file not found: {component_file}")
        
        with open(component_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def load_recipe(self, version: str = "latest") -> Dict[str, Any]:
        """レシピファイルを読み込み"""
        if version == "latest":
            available_versions = self.get_recipe_versions()
            if not available_versions:
                raise ValueError("No recipe files found")
            version = self.get_latest_version(available_versions)
        
        recipe_file = self.recipes_path / f"{version}.yaml"
        
        if not recipe_file.exists():
            raise FileNotFoundError(f"Recipe file not found: {recipe_file}")
        
        with open(recipe_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def resolve_recipe_components(self, recipe: Dict[str, Any]) -> Dict[str, Any]:
        """レシピ内のコンポーネントバージョンを解決"""
        resolved_recipe = recipe.copy()
        resolved_components = []
        
        for component_config in recipe.get('Components', []):
            for component_name, component_info in component_config.items():
                component_version = component_info.get('Version', 'x.x.x')
                
                # バージョンが x.x.x の場合は最新バージョンを取得
                if component_version == "x.x.x":
                    available_versions = self.get_component_versions(component_name)
                    if available_versions:
                        component_version = self.get_latest_version(available_versions)
                
                resolved_components.append({
                    component_name: {
                        'Version': component_version
                    }
                })
        
        resolved_recipe['Components'] = resolved_components
        return resolved_recipe


def get_imagebuilder_component_details(component_build_version_arn: str, region_name: str = 'ap-northeast-1') -> Optional[Dict[str, Any]]:
    """
    Image Builderコンポーネントの詳細を取得します。

    Args:
        component_build_version_arn (str): 取得したいコンポーネントのビルドバージョンARN。
                                           例: arn:aws:imagebuilder:...:component/MyComponent/1.0.0/1
        region_name (str): AWSリージョン名。デフォルトは 'ap-northeast-1'。

    Returns:
        Optional[Dict[str, Any]]: コンポーネントの詳細情報を含む辞書。
                                   コンポーネントが見つからない、またはエラーの場合はNone。
    """
    try:
        client = boto3.client('imagebuilder', region_name=region_name)
        response = client.get_component(componentBuildVersionArn=component_build_version_arn) # ここを修正
        
        # 'component' キーが存在すれば、その内容を返す
        if 'component' in response:
            return response['component']
        else:
            print(f"Warning: Component with ARN {component_build_version_arn} not found in response.")
            return None
            
    except client.exceptions.InvalidRequestException as e:
        print(f"Error: Invalid request for component {component_build_version_arn}. {e}")
        return None
    except client.exceptions.ClientError as e:
        # 例: ComponentNotFoundException など
        if e.response['Error']['Code'] == 'ComponentNotFoundException':
            print(f"Component with ARN {component_build_version_arn} not found.")
        else:
            print(f"An AWS client error occurred for component {component_build_version_arn}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for component {component_build_version_arn}: {e}")
        return None

def get_imagebuilder_recipe_details(recipe_arn: str, region_name: str = 'ap-northeast-1') -> Optional[Dict[str, Any]]:
    """
    Image Builderイメージレシピの詳細を取得します。
    (この関数は変更なし)

    Args:
        recipe_arn (str): 取得したいイメージレシピのARN。
        region_name (str): AWSリージョン名。デフォルトは 'ap-northeast-1'。

    Returns:
        Optional[Dict[str, Any]]: イメージレシピの詳細情報を含む辞書。
                                   レシピが見つからない、またはエラーの場合はNone。
    """
    try:
        client = boto3.client('imagebuilder', region_name=region_name)
        response = client.get_image_recipe(imageRecipeArn=recipe_arn)
        
        if 'imageRecipe' in response:
            return response['imageRecipe']
        else:
            print(f"Warning: Image recipe with ARN {recipe_arn} not found in response.")
            return None
            
    except client.exceptions.InvalidRequestException as e:
        print(f"Error: Invalid request for recipe {recipe_arn}. {e}")
        return None
    except client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ImageRecipeNotFoundException':
            print(f"Image recipe with ARN {recipe_arn} not found.")
        else:
            print(f"An AWS client error occurred for recipe {recipe_arn}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for recipe {recipe_arn}: {e}")
        return None


class ImageBuilderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, recipe_data: Dict[str, Any], 
                 components_data: Dict[str, Dict[str, Any]], **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.recipe_data = recipe_data
        self.components_data = components_data

        get_imagebuilder_component_details("arn:aws:imagebuilder:ap-northeast-1:897729135795:component/component1/1.0.0")
        get_imagebuilder_component_details("arn:aws:imagebuilder:ap-northeast-1:897729135795:component/component2/1.0.0")
        get_imagebuilder_recipe_details("arn:aws:imagebuilder:ap-northeast-1:897729135795:image-recipe/image-builder-test/1.0.1")
        
        # boto3 Imagebuilder クライアントを初期化
        print(self.region)
        self.imagebuilder_client = boto3.client('imagebuilder', region_name=self.region)
        
        # IAM Role for Image Builder
        self.image_builder_role = self._create_image_builder_role()
        
        # Instance Profile
        self.instance_profile = self._create_instance_profile()
        
        # Components
        self.components = self._create_components()
        
        # Recipe
        self.recipe = self._create_recipe()
        
        # Infrastructure Configuration
        self.infrastructure_config = self._create_infrastructure_config()
        
        # Distribution Configuration
        self.distribution_config = self._create_distribution_config()
        
        # Image Pipeline
        self.image_pipeline = self._create_image_pipeline()
        
        # Outputs
        self._create_outputs()
    
    def _create_image_builder_role(self) -> iam.Role:
        """Image Builder用のIAMロールを作成"""
        role = iam.Role(
            self, "ImageBuilderRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("EC2InstanceProfileForImageBuilder"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ]
        )
        
        # CloudWatch Logs への書き込み権限を追加
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        return role
    
    def _create_instance_profile(self) -> iam.CfnInstanceProfile:
        """インスタンスプロファイルを作成"""
        return iam.CfnInstanceProfile(
            self, "ImageBuilderInstanceProfile",
            roles=[self.image_builder_role.role_name]
        )
    
    def _get_existing_component_arn(self, name: str, version: str) -> Optional[str]:
        """
        指定された名前とバージョンの既存コンポーネントのARNを取得する。
        見つからない場合はNoneを返す。
        """
        try:
            # list_components API でフィルタリング
            response = self.imagebuilder_client.list_components(
                filters=[
                    {'name': 'name', 'values': [name]},
                    {'name': 'version', 'values': [version]}
                ]
            )
            
            print("componentList:")
            print(response.get('componentList', []))
            # ページネーションを考慮し、正確に一致するものを探す
            for component_summary in response.get('componentList', []):
                if component_summary['name'] == name and component_summary['version'] == version:
                    return component_summary['arn']
            return None
            
        except Exception as e:
            # エラー処理。権限がない場合など
            print(f"Warning: Could not list Image Builder components. Error: {e}", file=sys.stderr)
            return None

    def _get_existing_recipe_arn(self, name: str, version: str) -> Optional[str]:
        """
        指定された名前とバージョンの既存レシピのARNを取得する。
        見つからない場合はNoneを返す。
        """
        try:
            # 名前でフィルタリングし、全バージョンを取得
            paginator = self.imagebuilder_client.get_paginator('list_image_recipes')
            # 'name' フィルターは使用可能
            response_iterator = paginator.paginate(
                filters=[{'name': 'name', 'values': [name]}]
            )
            
            for page in response_iterator:
                print("imageRecipeList:")
                print(page.get('imageRecipeList', []))
                for recipe_summary in page.get('imageRecipeList', []):
                    # Pythonコード内でバージョンを比較
                    if recipe_summary['name'] == name and recipe_summary['version'] == version:
                        return recipe_summary['arn']
            return None
            
        except Exception as e:
            print(f"Warning: Could not list Image Builder recipes. Error: {e}", file=sys.stderr)
            return None
            
    def _create_components(self) -> Dict[str, Any]: # 戻り値の型を CfnComponent から Any に変更
        """コンポーネントを作成（既存の場合は参照）"""
        components = {}
        
        for component_name, component_data in self.components_data.items():
            version = component_data['Version']
            existing_arn = self._get_existing_component_arn(component_name, version)
            
            if existing_arn:
                print(f"Component '{component_name}' v{version}' already exists. Using ARN: {existing_arn}")
                # 既存のARNを使用するダミーオブジェクトを作成
                components[component_name] = ExistingImageBuilderComponent(existing_arn)
            else:
                print(f"Creating new Component '{component_name}' v{version}'...")
                component = imagebuilder.CfnComponent(
                    self, f"Component{component_name}",
                    name=component_data['Name'],
                    platform=component_data['Platform'],
                    version=component_data['Version'],
                    data=component_data['Data']
                )
                components[component_name] = component
        
        return components
    
    def _create_recipe(self) -> Any: # 戻り値の型を CfnImageRecipe から Any に変更
        """レシピを作成（既存の場合は参照）"""
        recipe_name = self.recipe_data['Name']
        recipe_version = self.recipe_data['Version']
        existing_arn = self._get_existing_recipe_arn(recipe_name, recipe_version)

        if existing_arn:
            print(f"Image Recipe '{recipe_name}' v{recipe_version}' already exists. Using ARN: {existing_arn}")
            return ExistingImageBuilderRecipe(existing_arn) # self.recipe に直接設定

        print(f"Creating new Image Recipe '{recipe_name}' v{recipe_version}'...")
        # コンポーネント参照を構築
        component_refs = []
        for component_config in self.recipe_data['Components']:
            for component_name, component_info in component_config.items():
                if component_name in self.components:
                    # ここで self.components[component_name] が ExistingImageBuilderComponent か CfnComponent のどちらかになる
                    component_refs.append(
                        imagebuilder.CfnImageRecipe.ComponentConfigurationProperty(
                            component_arn=self.components[component_name].attr_arn
                        )
                    )
        
        # ブロックデバイスマッピング
        block_device_mappings = []
        for mapping in self.recipe_data.get('BlockDeviceMappings', []):
            ebs_config = mapping.get('Ebs', {})
            block_device_mappings.append(
                imagebuilder.CfnImageRecipe.InstanceBlockDeviceMappingProperty(
                    device_name=mapping['DeviceName'],
                    ebs=imagebuilder.CfnImageRecipe.EbsInstanceBlockDeviceSpecificationProperty(
                        delete_on_termination=ebs_config.get('DeleteOnTermination', True),
                        volume_size=ebs_config.get('VolumeSize', 20), # 修正: VolumeSizeはint
                        volume_type=ebs_config.get('VolumeType', 'gp3') # 修正: VolumeTypeはstr
                    )
                )
            )
        
        return imagebuilder.CfnImageRecipe(
            self, "ImageRecipe",
            name=self.recipe_data['Name'],
            version=self.recipe_data['Version'],
            parent_image=f"arn:aws:imagebuilder:{self.region}:aws:image/{self.recipe_data['ParentImage']['Name']}/{self.recipe_data['ParentImage']['Version']}",
            components=component_refs,
            block_device_mappings=block_device_mappings if block_device_mappings else None
        )
    
    def _create_infrastructure_config(self) -> imagebuilder.CfnInfrastructureConfiguration:
        """インフラストラクチャ設定を作成"""
        # デフォルトVPCとサブネットを取得
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)
        
        # CloudWatch Logs Group
        log_group = logs.LogGroup(
            self, "ImageBuilderLogGroup",
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        return imagebuilder.CfnInfrastructureConfiguration(
            self, "InfrastructureConfig",
            name=f"{self.recipe_data['Name']}-infrastructure",
            instance_profile_name=self.instance_profile.ref,
            instance_types=["t3.medium"],
            subnet_id=vpc.public_subnets[0].subnet_id,
            security_group_ids=[
                "sg-0a43fd22ebc3702be", # このSGがImage Builderインスタンスからの必要な通信を許可しているか確認
            ],
            terminate_instance_on_failure=True,
            # logging=imagebuilder.CfnInfrastructureConfiguration.LoggingProperty(
            #     cloud_watch_logs=imagebuilder.CfnInfrastructureConfiguration.CloudWatchLogsProperty(
            #         log_group_name=log_group.log_group_name
            #     )
            # )
        )
    
    def _create_distribution_config(self) -> imagebuilder.CfnDistributionConfiguration:
        """配布設定を作成"""
        return imagebuilder.CfnDistributionConfiguration(
            self, "DistributionConfig",
            name=f"{self.recipe_data['Name']}-distribution",
            distributions=[
                imagebuilder.CfnDistributionConfiguration.DistributionProperty(
                    region=self.region,
                    ami_distribution_configuration=imagebuilder.CfnDistributionConfiguration.AmiDistributionConfigurationProperty(
                        name=f"{self.recipe_data['Name']} {{{{ imagebuilder:buildDate }}}}",
                        description=f"Generated by Image Builder Pipeline for {self.recipe_data['Name']}"
                    )
                )
            ]
        )
    
    def _create_image_pipeline(self) -> imagebuilder.CfnImagePipeline:
        """イメージパイプラインを作成"""
        return imagebuilder.CfnImagePipeline(
            self, "ImagePipeline",
            name=f"{self.recipe_data['Name']}-pipeline",
            image_recipe_arn=self.recipe.attr_arn, # ここで self.recipe が ExistingImageBuilderRecipe か CfnImageRecipe のどちらかになる
            infrastructure_configuration_arn=self.infrastructure_config.attr_arn,
            distribution_configuration_arn=self.distribution_config.attr_arn,
            status="ENABLED"
        )
    
    def _create_outputs(self):
        """スタックの出力を作成"""
        # ImagePipelineArn は CfnImagePipeline を作成した場合のみ出力
        if isinstance(self.image_pipeline, imagebuilder.CfnImagePipeline):
            CfnOutput(
                self, "ImagePipelineArn",
                value=self.image_pipeline.attr_arn,
                description="Image Builder Pipeline ARN"
            )
        # else:
        #     # ImagePipeline が既存の場合は ARN を取得する方法がないため、CfnOutput は出さないのが一般的
        #     # もし必要なら別の方法で ARN を取得して出力
        
        if isinstance(self.recipe, imagebuilder.CfnImageRecipe):
            CfnOutput(
                self, "ImageRecipeArn",
                value=self.recipe.attr_arn,
                description="Image Recipe ARN"
            )
        else: # ExistingImageBuilderRecipe の場合は attr_arn を利用
             CfnOutput(
                self, "ImageRecipeArn",
                value=self.recipe.attr_arn, 
                description="Image Recipe ARN (Existing)"
            )

def main():
    # 環境変数から設定を取得
    recipe_version = os.environ.get('RECIPE_VERSION', 'latest')
    
    try:
        # Image Builder Manager を初期化
        manager = ImageBuilderManager()
        
        # レシピを読み込み、コンポーネントバージョンを解決
        recipe_data = manager.load_recipe(recipe_version)
        resolved_recipe = manager.resolve_recipe_components(recipe_data)
        
        print(f"Loaded recipe: {resolved_recipe['Name']} v{resolved_recipe['Version']}")
        
        # 必要なコンポーネントを読み込み
        components_data = {}
        for component_config in resolved_recipe['Components']:
            for component_name, component_info in component_config.items():
                component_version = component_info['Version']
                component_data = manager.load_component(component_name, component_version)
                components_data[component_name] = component_data
                print(f"Loaded component: {component_name} v{component_version}")
        
        # CDK アプリケーションを作成
        app = cdk.App()
        
        # スタックを作成
        stack = ImageBuilderStack(
            app, 
            f"ImageBuilderStack-{resolved_recipe['Name'].replace('_', '-')}",
            recipe_data=resolved_recipe,
            components_data=components_data,
            env=cdk.Environment(
                account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
                region=os.environ.get('CDK_DEFAULT_REGION', 'ap-northeast-1')
            )
        )
        
        # CDK アプリケーションを実行
        app.synth()
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

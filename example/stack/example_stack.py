import os

from aws_cdk import (
    aws_apigateway as api_gw,
    aws_lambda as lambda_,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_iam as iam,
    Stack,
    CfnParameter,
    Fn,
    Aws,
    Duration,
)
from constructs import Construct


class CostLenzExampleStack(Stack):
    def __init__(self, scope: Construct, _id: str):
        super().__init__(
            scope,
            _id,
            env={
                "account": os.environ["CDK_DEFAULT_ACCOUNT"],
                "region": os.environ["CDK_DEFAULT_REGION"],
            },
        )

        param_vpc_id = CfnParameter(
            self,
            "vpcId",
            type="AWS::EC2::VPC::Id",
            description="VPC to connect the Lambda with",
        )
        param_subnet_id = CfnParameter(
            self,
            "subnetId",
            type="AWS::EC2::Subnet::Id",
            description="Subnet to connect the Lambda with",
        )

        api = api_gw.RestApi(
            self, "costlenz-example-api-gw", rest_api_name="CostLenz Example API"
        )

        queue = sqs.Queue(self, "costlenz-example-sqs-queue")

        # AWS managed Lambda layer (https://aws-otel.github.io/docs/getting-started/lambda)
        adot_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "adot-layer",
            f"arn:aws:lambda:{self.region}:901920570463:layer:aws-otel-python38-ver-1-7-1:1",
        )

        adot_config_layer = lambda_.LayerVersion(
            self,
            "adot-config-layer",
            code=lambda_.Code.from_asset("otel-config"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_8],
        )

        lambda_vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "costlenz-example-vpc",
            vpc_id=param_vpc_id.value_as_string,
            availability_zones=Fn.get_azs(),
            public_subnet_ids=[param_subnet_id.value_as_string],
            vpc_cidr_block=Aws.NO_VALUE,
        )

        lambda_role = iam.Role(
            self,
            "lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        lambda_role.add_to_principal_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=["*"],
                actions=[
                    "sqs:SendMessage",
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                ],
            )
        )

        lambda1 = lambda_.Function(
            self,
            "costlenz-example-lambda-1",
            function_name="CostLenzExampleLambda1",
            code=lambda_.Code.from_asset("lambda"),
            handler="lambda1.main",
            layers=[adot_layer, adot_config_layer], # use AWS managed Lambda layer
            runtime=lambda_.Runtime.PYTHON_3_8,
            timeout=Duration.seconds(15),
            environment=dict(
                AWS_LAMBDA_EXEC_WRAPPER="/opt/otel-instrument", # run Lambda extension from AWS managed Lambda layer
                SQS_QUEUE_URL=queue.queue_url,
                OPENTELEMETRY_COLLECTOR_CONFIG_FILE="/opt/python/collector.yaml", # provide configuration for OpenTelemetry
            ),
            tracing=lambda_.Tracing.ACTIVE,
            vpc=lambda_vpc,
            allow_public_subnet=True,
            role=lambda_role,
        )

        queue.grant_send_messages(lambda1)

        lambda_integration = api_gw.LambdaIntegration(lambda1)

        endpoint_resource = api.root.add_resource("lambda1")
        endpoint_resource.add_method("GET", lambda_integration)

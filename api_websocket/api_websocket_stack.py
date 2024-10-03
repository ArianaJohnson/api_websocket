from sys import api_version

import aws_cdk
from aws_cdk import (
    # Duration,
    Stack,
    Environment,
    # aws_sqs as sqs,
    aws_apigatewayv2 as apigatewayv2,
    aws_dynamodb as dynamodb,
    aws_lambda, Duration, RemovalPolicy, aws_iam, CfnOutput)
import os
dirname = os.path.dirname(__file__)
from aws_cdk.aws_iam import Effect

from constructs import Construct

class ApiWebsocketStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        api_version = aws_cdk.aws_apigateway.ApiKey.from_api_key_id(self, "imported-key", "<api-key-id")
        # example resource
        # queue = sqs.Queue(
        #     self, "HelloCdkQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
        cnf_api = apigatewayv2.CfnApi(self, "ApiGatewaysocket",
                              name = "ApiGatewaysocket",
                              protocol_type = "WEBSOCKET",
                              route_selection_expression =  "$request.body.action")


## table
        table = dynamodb.Table(self,"ConnectionIDTable",
                       partition_key=dynamodb.Attribute(
                       name="id",
                       type=dynamodb.AttributeType.STRING
                        ),
                       read_capacity = 7,
                       write_capacity = 7,
                       removal_policy= RemovalPolicy.DESTROY,
                       )


        #
        connect_function = aws_lambda.Function(self, "connect_func",
                                      code = aws_lambda.Code.from_asset(os.path.join(dirname, './../lambdas')),
                                      handler = "connect.handler",
                                      runtime = aws_lambda.Runtime.PYTHON_3_8,
                                      timeout = Duration.seconds(100),
                                      memory_size = 1024,
                                    )
        table.grant_read_write_data(connect_function)


        disconnect_function = aws_lambda.Function(self, "disconnect_func",
                                      code=aws_lambda.Code.from_asset(os.path.join(dirname, './../lambdas')),
                                      handler="disconnect.handler",
                                      runtime=aws_lambda.Runtime.PYTHON_3_8,
                                      timeout=Duration.seconds(100),
                                      memory_size=1024,
                                     environment={
                                                "TABLE_NAME": table.table_name
                                                  })

        table.grant_read_write_data(disconnect_function)


        message_function = aws_lambda.Function(self, "message_function",
                                              code=aws_lambda.Code.from_asset(os.path.join(dirname, './../lambdas')),
                                              handler="send_message.handler",
                                              runtime=aws_lambda.Runtime.PYTHON_3_8,
                                               timeout=Duration.seconds(100),
                                               memory_size=1024,
                                               environment={
                                                   "TABLE_NAME": table.table_name,
                                                   "ENDPOINT": f"https://{cnf_api}.execute-api.{self.region}.amazonaws.com/dev",
                                               },


                                               initial_policy= [ aws_iam.PolicyStatement(
                                                   #effect=[aws_iam.Effect.ALLOW],
                                                   actions = ["excecute-api:ManageConnections"],
                                                   resources = ["*"])
                                               ])

        role = aws_iam.Role(self, "SelfForRoleApiGwInvokeLambda",
                                role_name="SelfForRoleApiGwInvokeLambda",
                                assumed_by=aws_iam.ServicePrincipal('apigateway.amazonaws.com'))



        role.add_to_policy(aws_iam.PolicyStatement(
            resources=[connect_function.function_arn,
                       disconnect_function.function_arn,
                       message_function.function_arn
                       ],
            actions = ["lambda:InvokeFunction"]
        ))

        table.grant_read_write_data(message_function)



        connection_integration = apigatewayv2.CfnIntegration(self, "connect_lambda",
                                                             api_id = api_version.to_string(),
                                                             integration_type= "AWS_PROXY",
                                                             integration_uri= "",
                                                             credentials_arn= role.role_arn)

        disconnect_integration = apigatewayv2.CfnIntegration(self, "disconnect_lambda",
                                                             api_id= api_version.to_string(),
                                                             integration_type="AWS_PROXY",
                                                             integration_uri= "",
                                                             credentials_arn=role.role_arn)

        msg_integration = apigatewayv2.CfnIntegration(self, "msg_lambda",
                                                             api_id=cnf_api.to_string(),
                                                             integration_type="AWS_PROXY",
                                                             integration_uri = "",
                                                             credentials_arn=role.role_arn)



        connect_route = apigatewayv2.CfnRoute(self, "connect_route",
                                              api_id= api_version.to_string(),
                                              route_key = "$connect",
                                              authorization_type= "NONE",
                                              target= "integrations/" + connection_integration.ref)

        disconnect_route = apigatewayv2.CfnRoute(self, "disconnect_route",
                                              api_id=api_version.to_string(),
                                              route_key="$disconnect",
                                              authorization_type="NONE",
                                              target="integrations/" + disconnect_integration.ref)

        message_route = apigatewayv2.CfnRoute(self, "message_route",
                                              api_id = api_version.to_string(),
                                              route_key="sendmessage",
                                              authorization_type="NONE",
                                              target="integrations/" + msg_integration.ref)




        #deploy
        deployment = apigatewayv2.CfnDeployment(self, "deployment",
                                                api_id=api_version.to_string(),)

        development_stage = apigatewayv2.CfnStage(self, "development_stage",
                                                  stage_name="development",
                                                  deployment_id= deployment.ref,
                                                  api_id=api_version.to_string(),
                                                  )


        ##add the dependencies

        deployment.node.add_dependency(connect_route)
        deployment.node.add_dependency(message_route)
        deployment.node.add_dependency(disconnect_route)

        # wss_endpoint = CfnOutput(self, "wss_endpoint",
        #                              export_name= "wss_endpoint",
        #                              value= "wss://" + api_version.to_string() + ".execute-api." + self.region +".com/dev")
        #




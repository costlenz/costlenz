import json
import boto3
import os
import time

from opentelemetry import trace

sqs = boto3.client(
    "sqs", endpoint_url=f"https://sqs.{os.environ['AWS_REGION']}.amazonaws.com"
)

tracer = trace.get_tracer(__name__)


def response(http_status, body):
    return {
        "statusCode": http_status,
        "body": body,
        "headers": {
            "Content-Type": "application/json",
        },
    }


def main(event, context):
    print(event)

    if "queryStringParameters" in event and "tenant" in event["queryStringParameters"]:
        tenant_id = event["queryStringParameters"]["tenant"]
    else:
        tenant_id = int(time.time() * 1000) % 10

    msg = {"payload_for_tenant": tenant_id}

    current_span = trace.get_current_span()
    current_span.set_attribute("tenant_id", tenant_id)

    current_span.set_attribute(
        "application_id", "costlenz-example"
    )  # overriding default value

    # current_span.set_attribute(
    #     "resource_id", "lambda_ARN"
    # )
    # # Set resource ID manually.
    # # Not required, because Lambda in this example instrumented with AWS distribution for OpenTelemetry

    sqs.send_message(
        QueueUrl=os.environ["SQS_QUEUE_URL"], MessageBody=(json.dumps(msg))
    )

    return response(200, json.dumps(msg))

    return response

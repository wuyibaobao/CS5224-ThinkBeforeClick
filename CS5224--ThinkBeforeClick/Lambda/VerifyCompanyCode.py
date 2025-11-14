import os, json, base64, logging
import boto3
from botocore.exceptions import ClientError

log = logging.getLogger()
log.setLevel(logging.INFO)

TABLE = os.getenv("TABLE_NAME", "ThinkBeforeClick-CompanyVerificationCodes")
REGION = os.getenv("AWS_REGION")

ddb = boto3.client("dynamodb", region_name=REGION)

def resp(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }

def get_code(event):
    # JSON body
    if event.get("body"):
        raw = event["body"]
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        try:
            return (json.loads(raw).get("code") or "").strip()
        except json.JSONDecodeError:
            return ""
    # or query string ?code=...
    qs = event.get("queryStringParameters") or {}
    return (qs.get("code") or "").strip()

def lambda_handler(event, context):
    # Preflight
    if event.get("httpMethod") == "OPTIONS":
        return resp(200, {"ok": True})

    code = get_code(event)
    if not code:
        return resp(400, {"ok": False, "message": "Missing 'code'.", "status": "error"})

    try:
        r = ddb.get_item(
            TableName=TABLE,
            Key={"code": {"S": code}},
            ConsistentRead=True
        )
        item = r.get("Item")
        if not item:
            return resp(200, {"ok": True, "message": "Code not found.", "status": "not_found"})

        status = (item.get("status", {}).get("S") or "").lower()
        return resp(200, {
            "ok": True,
            "message": "Code is valid." if status == "valid" else "Code is not valid.",
            "status": status if status else "invalid"
        })

    except ClientError as e:
        # This will help you see the *exact* AWS error in the response while you debug
        err = e.response["Error"].get("Code", "ClientError")
        log.exception("DynamoDB error")
        return resp(500, {"ok": False, "message": "DynamoDB error", "status": "error", "code": err})
    except Exception as e:
        log.exception("Unhandled error")
        return resp(500, {"ok": False, "message": "Server error", "status": "error"})

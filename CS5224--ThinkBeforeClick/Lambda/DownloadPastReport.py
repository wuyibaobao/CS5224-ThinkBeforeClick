# lambda_download_company_report.py
import os, json, boto3
from botocore.config import Config

BUCKET        = os.environ["REPORTS_BUCKET"]
REGION        = "ap-southeast-1"
REPORT_ROOT   = os.environ.get("REPORTS_PREFIX", "enterprise/report/")
PRESIGNED_TTL = 300

s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"))

def _cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS"
    }

def _bad(msg, code=400):
    return {"statusCode": code, "headers": _cors(), "body": json.dumps({"error": msg})}

def lambda_handler(event, _ctx):
    cid = (event.get("pathParameters") or {}).get("companyId") or ""
    q = event.get("queryStringParameters") or {}
    name = (q.get("name") or "").strip()

    if not cid or not name:
        return _bad("companyId and name are required")

    if "/" in name or "\\" in name or ".." in name:
        return _bad("invalid name")

    key = f"{REPORT_ROOT}{cid}/{name}"

    try:
        s3.head_object(Bucket=BUCKET, Key=key)
    except Exception:
        return _bad("not found", 404)

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=PRESIGNED_TTL,
    )

    return {
        "statusCode": 302,
        "headers": {**_cors(), "Location": url}
    }

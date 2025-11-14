# lambda_list_company_reports.py
import os, json, posixpath, boto3
from botocore.config import Config
from datetime import datetime, timezone

BUCKET       = os.environ["REPORTS_BUCKET"]
REGION       = "ap-southeast-1"
REPORT_ROOT  = os.environ.get("REPORTS_PREFIX", "enterprise/report/")

s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"))

def _cors():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS"
    }

def _resp(status, body):
    return {"statusCode": status, "headers": _cors(), "body": json.dumps(body)}

def lambda_handler(event, _ctx):
    pp = (event.get("pathParameters") or {})
    qs = (event.get("queryStringParameters") or {})
    cid = (
        pp.get("companyId") or pp.get("company-id") or pp.get("id") or
        qs.get("companyId") or qs.get("company-id") or qs.get("id")
    )
    if not cid:
        return _resp(400, {"error": "companyId required"})


    prefix = f"{REPORT_ROOT}{cid}/"
    items = []

    paginator = s3.get_paginator("list_objects_v2")
    total = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            total += 1
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                items.append({
                    "name": posixpath.basename(key),
                    "size": obj.get("Size", 0),
                    "lastModified": obj.get("LastModified").astimezone(timezone.utc).isoformat()
                })

    items.sort(key=lambda r: r["lastModified"], reverse=True)

    print(f"[history] companyId={cid} prefix={prefix} total={total} pdfs={len(items)}")

    return _resp(200, items)

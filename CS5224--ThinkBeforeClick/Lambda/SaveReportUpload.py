import json, os, base64, datetime
import boto3

s3 = boto3.client('s3')
BUCKET = os.environ.get('REPORTS_BUCKET')
PREFIX = os.environ.get('REPORTS_PREFIX')

def lambda_handler(event, context):
    try:
        path_params = event.get('pathParameters') or {}
        company_id = path_params.get('companyId')
        if not company_id:
            return _resp(400, {"error": "companyId path param is required"})

        body = json.loads(event.get('body') or '{}')
        pdf_b64 = body.get('pdfBase64') 
        if not pdf_b64:
            return _resp(400, {"error": "pdfBase64 is required"})

        if ',' in pdf_b64:
            pdf_b64 = pdf_b64.split(',', 1)[1]

        pdf_bytes = base64.b64decode(pdf_b64)

        ts = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        filename = f"company_{ts}.pdf"
        key = f"{PREFIX}{company_id}/{filename}"

        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            Metadata={"companyId": company_id, "timestamp": ts}
        )

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600
        )
        return _resp(200, {"message": "saved", "key": key, "downloadUrl": url})
    except Exception as e:
        print("ERR:", e)
        return _resp(500, {"error": "internal_error", "message": str(e)})

def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body)
    }

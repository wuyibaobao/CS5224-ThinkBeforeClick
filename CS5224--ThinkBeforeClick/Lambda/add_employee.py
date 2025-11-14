# lambda_function.py
import json, os, uuid, logging, random
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

log = logging.getLogger()
log.setLevel(logging.INFO)

EMPLOYEES_TABLE          = os.getenv("EMPLOYEES_TABLE", "ThinkBeforeClick-Employees")
USERS_TABLE              = os.getenv("USERS_TABLE",     "ThinkBeforeClick-Users")
COGNITO_USER_POOL_ID     = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_DEFAULT_PASSWORD = os.getenv("COGNITO_DEFAULT_PASSWORD")
AWS_REGION               = os.getenv("AWS_REGION")

COGNITO_REGION = (COGNITO_USER_POOL_ID.split("_")[0]
                  if COGNITO_USER_POOL_ID and "_" in COGNITO_USER_POOL_ID
                  else AWS_REGION)

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
cognito  = boto3.client("cognito-idp", region_name=COGNITO_REGION)

def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type":"application/json","Access-Control-Allow-Origin":"*"},
        "body": json.dumps(body),
    }

def _gen_username():
    return f"user_{random.getrandbits(28):07x}"

def _get_sub_from_user_record(user_obj):
    for a in user_obj.get("Attributes", []):
        if a["Name"] == "sub":
            return a["Value"]
    return None

def _ensure_cognito_user_first(email: str) -> dict:
    """Find or create Cognito user by email; return {username, sub, created}."""
    if not COGNITO_USER_POOL_ID:
        return {"error":"InvalidConfig","message":"Missing COGNITO_USER_POOL_ID"}

    try:
        found = cognito.list_users(
            UserPoolId=COGNITO_USER_POOL_ID,
            Filter=f'email = "{email}"',
            Limit=1
        )
        if found["Users"]:
            u = found["Users"][0]
            username = u["Username"]
            sub = _get_sub_from_user_record(u)
            if not sub:
                got = cognito.admin_get_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
                sub = _get_sub_from_user_record({"Attributes": got.get("UserAttributes", [])})
            return {"username": username, "sub": sub, "created": False}
    except ClientError as e:
        err = e.response["Error"]
        return {"error": err.get("Code"), "message": err.get("Message"), "stage":"ListUsers"}

    username = _gen_username()
    try:
        cognito.admin_create_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "True"}
            ],
            MessageAction="SUPPRESS"
        )
    except cognito.exceptions.UsernameExistsException:
        username = _gen_username()
        cognito.admin_create_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "True"}
            ],
            MessageAction="SUPPRESS"
        )
    except cognito.exceptions.AliasExistsException:
        found = cognito.list_users(
            UserPoolId=COGNITO_USER_POOL_ID,
            Filter=f'email = "{email}"',
            Limit=1
        )
        if found["Users"]:
            u = found["Users"][0]
            return {"username": u["Username"], "sub": _get_sub_from_user_record(u), "created": False}
        return {"error":"AliasExistsException","message":"Email already used but user not found","stage":"Create"}
    except ClientError as e:
        err = e.response["Error"]
        return {"error": err.get("Code"), "message": err.get("Message"), "stage":"AdminCreateUser"}

    try:
        cognito.admin_set_user_password(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username,
            Password=COGNITO_DEFAULT_PASSWORD,
            Permanent=True
        )
    except ClientError as e:
        err = e.response["Error"]
        return {"error": err.get("Code"), "message": err.get("Message"), "stage":"AdminSetUserPassword"}

    # Get sub
    try:
        got = cognito.admin_get_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
        sub = _get_sub_from_user_record({"Attributes": got.get("UserAttributes", [])})
        return {"username": username, "sub": sub, "created": True}
    except ClientError as e:
        err = e.response["Error"]
        return {"error": err.get("Code"), "message": err.get("Message"), "stage":"AdminGetUser"}

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        company_id = (body.get("companyId") or "").strip()
        name       = (body.get("name") or "").strip()
        email      = (body.get("email") or "").strip().lower()

        if not all([company_id, name, email]):
            return _resp(400, {"error":"Missing required fields","required":["companyId","name","email"]})

        users_tbl     = dynamodb.Table(USERS_TABLE)
        employees_tbl = dynamodb.Table(EMPLOYEES_TABLE)

        cog = _ensure_cognito_user_first(email)
        if "error" in cog:
            return _resp(502, {"error":"CognitoFailed","details":cog})
        cognito_username = cog["username"]
        cognito_sub      = cog["sub"]

        employee_id = f"emp_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.utcnow().isoformat()

        try:
            users_tbl.put_item(
                Item={
                    "userId": cognito_sub,
                    "accountType": "employee",
                    "companyId": company_id,
                    "email": email,
                    "employeeId": employee_id,
                    "cognitoUsername": cognito_username,
                    "createdAt": now_iso
                },
                ConditionExpression="attribute_not_exists(userId)"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                users_tbl.update_item(
                    Key={"userId": cognito_sub},
                    UpdateExpression=(
                        "SET accountType=:t, companyId=:c, email=:e, "
                        "employeeId=:eid, cognitoUsername=:u"
                    ),
                    ExpressionAttributeValues={
                        ":t":"employee", ":c":company_id, ":e":email,
                        ":eid":employee_id, ":u":cognito_username
                    }
                )
            else:
                raise

        dup = employees_tbl.scan(
            FilterExpression=Attr("companyId").eq(company_id) & Attr("email").eq(email)
        ).get("Items", [])
        if dup:
            return _resp(409, {"error":"Employee with this email already exists","existingEmployee":dup[0]})

        emp_item = {
            "employeeId": employee_id,
            "companyId": company_id,
            "name": name,
            "email": email,
            "addedAt": now_iso,
            "sentEmails": 0,
            "openedEmails": 0,
            "clickedScams": 0
        }
        employees_tbl.put_item(Item=emp_item)

        return _resp(200, {
            "message": "Employee added",
            "employee": emp_item,
            "user": {
                "userId": cognito_sub,
                "accountType": "employee",
                "companyId": company_id,
                "email": email,
                "employeeId": employee_id,
                "cognitoUsername": cognito_username
            }
        })

    except Exception as e:
        log.exception("Unhandled error")
        return _resp(500, {"error":"Internal server error","message":str(e)})

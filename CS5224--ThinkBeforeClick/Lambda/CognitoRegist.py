import json
import boto3
import logging
import uuid
import os 

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')


USER_POOL_ID = os.environ['USER_POOL_ID']
CLIENT_ID = os.environ['CLIENT_ID']
USERS_TABLE_NAME = os.environ['USERS_TABLE_NAME']
COMPANIES_TABLE_NAME = os.environ['COMPANIES_TABLE_NAME']

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Credentials": "true"
    }

    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", {})

        email = body.get("username")
        password = body.get("password")
        attributes = body.get("attributes", {})

        if not email or not password:
            raise ValueError("Missing 'username' or 'password' in request body")


        username = f"user_{str(uuid.uuid4())[:8]}"
        logger.info("Generated username: %s for email: %s", username, email)

        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "preferred_username", "Value": username},
        ]

        user_type = attributes.get("custom:user_type", "individual")

        if user_type == "individual":
            user_attributes.append({"Name": "custom:user_type", "Value": "individual"})
            user_attributes.append({"Name": "custom:role", "Value": "member"})

        elif user_type == "enterprise":
            org_type = attributes.get("custom:organization_type", "general")
            admin_username = attributes.get("custom:admin_username", username)
            role = attributes.get("custom:role", "admin")

            user_attributes.extend([
                {"Name": "custom:user_type", "Value": "enterprise"},
                {"Name": "custom:organization_type", "Value": org_type},
                {"Name": "custom:admin_username", "Value": admin_username},
                {"Name": "custom:role", "Value": role},
            ])

        logger.info("Final user attributes: %s", json.dumps(user_attributes, ensure_ascii=False))

        response = cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=user_attributes
        )

        logger.info("✅ Cognito sign_up success: %s", json.dumps(response, default=str))

        user_sub_id = response['UserSub'] 

        users_table = dynamodb.Table(USERS_TABLE_NAME)
        company_id = None

        if user_type == "enterprise":

            logger.info("Enterprise user detected. Writing to Users and Companies tables.")

            company_id = attributes.get("custom:admin_username")

            organization_type = attributes.get("custom:organization_type")
            
            if not company_id:
                raise ValueError("Enterprise registration missing 'custom:admin_username'")

            companies_table = dynamodb.Table(COMPANIES_TABLE_NAME)
            company_item = {
                'companyId': company_id, #
                'domain': organization_type  #
            }

            company_item_cleaned = {k: v for k, v in company_item.items() if v is not None}
            companies_table.put_item(Item=company_item_cleaned)
            logger.info("✅ Wrote to Companies table: %s", company_id)

            user_item = {
                'userId': user_sub_id,         #
                'accountType': user_type,      #
                'companyId': company_id,     #
                'email': email,
                'cognitoUsername': username               #
            }
            users_table.put_item(Item=user_item)
            logger.info("✅ WWrote enterprise user to Users table: %s", user_sub_id)

        else:
            logger.info("Individual user detected. Writing to Users table only.")

            user_item = {
                'userId': user_sub_id,       #
                'accountType': 'individual', #
                'email': email,
                'cognitoUsername': username             #

            }
            users_table.put_item(Item=user_item)
            logger.info("✅ Wrote individual user to Users table: %s", user_sub_id)
        

        return {
            "statusCode": 200,
            "headers": headers, 
            "body": json.dumps({
                "message": "Registration successful! Please check your email for verification.",
                "userSub": user_sub_id
            })
        }

    except cognito.exceptions.UsernameExistsException:
        logger.error("❌ UsernameExistsException: Username already registered")
        return { "statusCode": 400, "headers": headers, "body": json.dumps({"error": "Username already exists."}) }
    except cognito.exceptions.InvalidParameterException as e:
        logger.error("❌ InvalidParameterException: %s", str(e))
        error_message = str(e)
        if "email" in str(e).lower(): error_message = "An account with this email already exists."
        return { "statusCode": 400, "headers": headers, "body": json.dumps({"error": error_message}) }
    except ValueError as e:
        logger.error("❌ ValueError: %s", str(e))
        return { "statusCode": 400, "headers": headers, "body": json.dumps({"error": str(e)}) }
        
    except Exception as e:
        logger.error("💥 Unexpected error (Could be Cognito OR DynamoDB failure): %s", str(e))
        

        
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Registration failed during database operation. Please contact support."})
        }
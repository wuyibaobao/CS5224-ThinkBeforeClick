import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')

USER_POOL_ID = "ap-southeast-1_r5HpqqhcN"
CLIENT_ID = "6qful1liesvrl612golldvmdl3"

def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Credentials": "true"
    }

    logger.info("📦 Full event received: %s", json.dumps(event))

    try:

        if event.get('httpMethod') == 'OPTIONS':
            return {
                "statusCode": 200, 
                "headers": headers, 
                "body": json.dumps({"message": "CORS preflight"})
            }
        

        body = {}
        if 'body' in event:
            if event.get('isBase64Encoded', False):
                import base64
                body_str = base64.b64decode(event['body']).decode('utf-8')
            else:
                body_str = event['body']
            
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                logger.error("❌ Failed to parse JSON body: %s", body_str)


        username = body.get("username", "").strip()
        password = body.get("password", "").strip()
        user_type = body.get("userType", "").strip()

        logger.info("👤 Extracted credentials - Username: '%s', UserType: '%s', Password present: %s", 
                   username, user_type, bool(password))

        if not username or not password:
            return {
                "statusCode": 400, 
                "headers": headers, 
                "body": json.dumps({
                    "message": "Username and password are required",
                    "debug": {
                        "username_received": username,
                        "userType_received": user_type,
                        "password_received": bool(password)
                    }
                })
            }


        actual_login_username = username
        
        if user_type == 'enterprise':
            logger.info("🏢 Enterprise user detected, searching for user with admin_username: %s", username)
            
            try:

                found_user = None
                paginator = cognito.get_paginator('list_users')
                
                for page in paginator.paginate(UserPoolId=USER_POOL_ID):
                    for user in page['Users']:

                        user_attrs = {attr['Name']: attr['Value'] for attr in user.get('Attributes', [])}
                        admin_username = user_attrs.get('custom:admin_username', '').strip()
                        
                        if admin_username == username:
                            found_user = user
                            break
                    if found_user:
                        break
                
                if found_user:

                    user_attrs = {attr['Name']: attr['Value'] for attr in found_user.get('Attributes', [])}
                    user_email = user_attrs.get('email', '').strip()
                    
                    if user_email:
                        actual_login_username = user_email
                        user_type_attr = user_attrs.get('custom:user_type', '').strip()
                        
                        logger.info("✅ Found enterprise user - Email: %s, Admin username: %s, User type: %s", 
                                   actual_login_username, username, user_type_attr)
                    else:
                        logger.error("❌ Enterprise user found but no email attribute: %s", found_user['Username'])
                        return {
                            "statusCode": 401,
                            "headers": headers,
                            "body": json.dumps({"message": "Enterprise user configuration error: email not found"})
                        }
                else:
                    logger.error("❌ No enterprise user found with admin_username: %s", username)
                    return {
                        "statusCode": 401,
                        "headers": headers,
                        "body": json.dumps({"message": "Enterprise user not found"})
                    }
                
            except Exception as e:
                logger.error("💥 Error searching for enterprise user: %s", str(e), exc_info=True)
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({"message": "Error processing enterprise user: " + str(e)})
                }
        else:
            
            logger.info("👤 Individual user, using username directly: %s", username)

        logger.info("🔐 Attempting Cognito login for user: %s (actual login username: %s)", 
                   username, actual_login_username)


        auth_response = cognito.admin_initiate_auth(
            UserPoolId=USER_POOL_ID,
            ClientId=CLIENT_ID,
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                "USERNAME": actual_login_username, 
                "PASSWORD": password
            }
        )


        user_response = cognito.admin_get_user(
            UserPoolId=USER_POOL_ID, 
            Username=actual_login_username
        )
        attrs = {a['Name']: a['Value'] for a in user_response['UserAttributes']}


        user_data = {
            "username": attrs.get("email", actual_login_username),
            "email": attrs.get("email", actual_login_username),
            "userType": attrs.get("custom:user_type", "individual"),
            "role": attrs.get("custom:role", "member"),
            "userStatus": user_response.get("UserStatus", "UNKNOWN"),
            "adminUsername": attrs.get("custom:admin_username", ""),
            "organizationType": attrs.get("custom:organization_type", ""),
            "originalUsername": username  
        }

        logger.info("✅ Login successful - Original: %s, Actual: %s", 
                   username, actual_login_username)
        

        return {
            "statusCode": 200, 
            "headers": headers, 
            "body": json.dumps(user_data)
        }


    except cognito.exceptions.NotAuthorizedException:
        logger.error("❌ NotAuthorizedException for user: %s (actual: %s)", 
                   username, actual_login_username if 'actual_login_username' in locals() else username)
        return {
            "statusCode": 401, 
            "headers": headers, 
            "body": json.dumps({"message": "Incorrect username or password"})
        }
    except cognito.exceptions.UserNotFoundException:
        logger.error("❌ UserNotFoundException for user: %s (actual: %s)", 
                   username, actual_login_username if 'actual_login_username' in locals() else username)
        return {
            "statusCode": 401, 
            "headers": headers, 
            "body": json.dumps({"message": "User not found"})
        }
    except cognito.exceptions.UserNotConfirmedException:
        logger.error("❌ UserNotConfirmedException for user: %s (actual: %s)", 
                   username, actual_login_username if 'actual_login_username' in locals() else username)
        return {
            "statusCode": 403, 
            "headers": headers, 
            "body": json.dumps({"message": "Please verify your email address"})
        }
    except Exception as e:
        logger.error("💥 Unexpected error: %s", str(e), exc_info=True)
        return {
            "statusCode": 500, 
            "headers": headers, 
            "body": json.dumps({"message": "Login failed: " + str(e)})
        }
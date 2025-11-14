import json
import boto3
import logging
import uuid
import os  # 👉 --- 新增：导入os库 ---

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cognito = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb') # 👉 --- 新增：初始化DynamoDB ---

# 👉 --- 修改：从环境变量读取，不再硬编码 ---
USER_POOL_ID = os.environ['USER_POOL_ID']
CLIENT_ID = os.environ['CLIENT_ID']
USERS_TABLE_NAME = os.environ['USERS_TABLE_NAME']       # 👉 --- 新增：Users表名 (e.g., "ThinkBeforeClick-Users") ---
COMPANIES_TABLE_NAME = os.environ['COMPANIES_TABLE_NAME'] # 👉 --- 新增：Companies表名 (e.g., "ThinkBeforeClick-Companies") ---

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

        # 👉 --- 【强烈建议删除】---
        # 下面这个 try/except 块是多余的、低效的。
        # cognito.sign_up 会自动检查Email是否已存在。
        # try:
        #     response = cognito.list_users(...)
        #     ...
        # except Exception as e:
        #     ...
        # 👉 --- 【删除结束】---

        username = f"user_{str(uuid.uuid4())[:8]}"
        logger.info("Generated username: %s for email: %s", username, email)

        user_attributes = [
            {"Name": "email", "Value": email},
            {"Name": "preferred_username", "Value": username},
        ]

        user_type = attributes.get("custom:user_type", "individual")

        # (这部分逻辑保留不变)
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

        # 步骤 1: Cognito sign_up 
        response = cognito.sign_up(
            ClientId=CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=user_attributes
        )

        logger.info("✅ Cognito sign_up success: %s", json.dumps(response, default=str))

        # 👇 --- 【这就是你的新任务：连接两个DynamoDB表】--- 👇

        # 步骤 2: 从Cognito响应中获取唯一的、永久的用户ID (Subject)
        # 这对应 Cognito 截图中的 'sub'
        user_sub_id = response['UserSub'] 

        # 步骤 3: 准备写入 DynamoDB
        users_table = dynamodb.Table(USERS_TABLE_NAME)
        company_id = None # 默认为 None

        # 步骤 4: 根据用户类型，执行不同逻辑
        if user_type == "enterprise":
            # ---------------------------------
            # A. 处理企业用户 (写两张表)
            # ---------------------------------
            logger.info("Enterprise user detected. Writing to Users and Companies tables.")
            
            # 从 'attributes' 中获取公司信息
            # 这对应 Cognito 截图中的 'custom:admin_username'
            company_id = attributes.get("custom:admin_username")
            # 这对应 Cognito 截图中的 'custom:organization_type'
            organization_type = attributes.get("custom:organization_type")
            
            if not company_id:
                raise ValueError("Enterprise registration missing 'custom:admin_username'")

            # 1. 准备写入 Companies 表
            companies_table = dynamodb.Table(COMPANIES_TABLE_NAME)
            company_item = {
                'companyId': company_id, #
                'domain': organization_type  # 映射到 'domain' 字段
            }
            # 清理 None 值
            company_item_cleaned = {k: v for k, v in company_item.items() if v is not None}
            companies_table.put_item(Item=company_item_cleaned)
            logger.info("✅ Wrote to Companies table: %s", company_id)

            # 2. 准备写入 Users 表（企业用户版）
            user_item = {
                'userId': user_sub_id,         #
                'accountType': user_type,      #
                'companyId': company_id,     #
                'email': email,
                'cognitoUsername': username               #
                # 'employeeId' 字段 看似是给非管理员的，这里不填
            }
            users_table.put_item(Item=user_item)
            logger.info("✅ WWrote enterprise user to Users table: %s", user_sub_id)

        else:
            # ---------------------------------
            # B. 处理个人用户 (只写一张表)
            # ---------------------------------
            logger.info("Individual user detected. Writing to Users table only.")
            
            # 1. 准备写入 Users 表（个人用户版）
            user_item = {
                'userId': user_sub_id,       #
                'accountType': 'individual', #
                'email': email,
                'cognitoUsername': username             #
                # companyId 和 employeeId 保持为 NULL (即不写入)
            }
            users_table.put_item(Item=user_item)
            logger.info("✅ Wrote individual user to Users table: %s", user_sub_id)
        
        # 👆 --- 【连接代码结束】--- 👆
        
        # 步骤 5: 全部成功后，才返回200
        return {
            "statusCode": 200,
            "headers": headers, 
            "body": json.dumps({
                "message": "Registration successful! Please check your email for verification.",
                "userSub": user_sub_id
            })
        }

    # ... (UsernameExistsException 和 InvalidParameterException 保留不变) ...
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
        # 👉 --- 【修改：这个错误现在可能是DynamoDB写入失败】--- 
        logger.error("💥 Unexpected error (Could be Cognito OR DynamoDB failure): %s", str(e))
        
        # 生产级代码应在这里添加补偿逻辑：
        # 尝试调用 cognito.admin_delete_user(...) 来删除刚创建的Cognito用户
        # 以防止数据不一致。
        
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Registration failed during database operation. Please contact support."})
        }
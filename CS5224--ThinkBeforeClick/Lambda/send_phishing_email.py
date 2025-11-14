"""
Lambda Function: Send Phishing Email
Triggers: API Gateway POST /api/send-phishing

This function sends phishing simulation emails to employees and creates tracking records.
"""

import json
import boto3
import uuid
from datetime import datetime
import os

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
EMPLOYEES_TABLE = os.environ.get('EMPLOYEES_TABLE', 'ThinkBeforeClick-Employees')
EMAIL_TRACKING_TABLE = os.environ.get('EMAIL_TRACKING_TABLE', 'ThinkBeforeClick-EmailTracking')
CLOUDFRONT_DOMAIN = os.environ.get('CLOUDFRONT_DOMAIN', 'd28hvr7wd2iqek.cloudfront.net')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@thinkbeforeclick.com')

# Template metadata
TEMPLATES = {
    'template1': {
        'name': 'DBS Bank Account Security Alert',
        'subject': '⚠️ URGENT: Suspicious Activity Detected on Your DBS Account',
        'from_name': 'DBS Bank Security Team'
    },
    'template2': {
        'name': 'SingPost Parcel Delivery',
        'subject': '📦 SingPost Delivery Notification - Customs Fee Required',
        'from_name': 'SingPost Delivery Service'
    },
    'template3': {
        'name': 'IRAS Tax Refund',
        'subject': '💰 IRAS Tax Refund Notice - S$1,247.80 Pending',
        'from_name': 'IRAS Tax Refund Department'
    },
    'template4': {
        'name': 'Shopee Lucky Draw',
        'subject': '🎉 Congratulations! You Won S$888 Shopee Voucher!',
        'from_name': 'Shopee Promotions Team'
    },
    'template5': {
        'name': 'LinkedIn Job Offer',
        'subject': '💼 Urgent: CPF Account Update Required for Job Application',
        'from_name': 'LinkedIn Jobs & CPF'
    },
    'template6': {
        'name': 'SP Group Utilities Refund',
        'subject': '💰 SP Group - Utilities Refund Notice for Your Account',
        'from_name': 'SP Group Billing Department'
    },
    'template7': {
        'name': 'LTA Traffic Fine',
        'subject': '⚠️ LTA Traffic Offence Notice - Payment Required',
        'from_name': 'Land Transport Authority'
    },
    'template8': {
        'name': 'PropertyGuru Investment',
        'subject': '🏢 Exclusive Pre-Launch: Marina Bay Luxury Residences',
        'from_name': 'PropertyGuru Investment Opportunities'
    },
    'template9': {
        'name': 'NUS Tuition Refund',
        'subject': '💰 NUS Tuition Fee Refund - S$1,850 Available',
        'from_name': 'NUS Office of Financial Services'
    },
    'template10': {
        'name': 'Carousell Payment Received',
        'subject': '✓ Carousell: Payment Received - Action Required',
        'from_name': 'Carousell Notifications'
    }
}

def lambda_handler(event, context):
    """
    Main Lambda handler function
    
    Expected input:
    {
        "companyId": "company-123",
        "employeeId": "emp-456",
        "employeeEmail": "john.doe@company.com",
        "employeeName": "John Doe",
        "templateId": "template1"
    }
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        company_id = body.get('companyId')
        employee_id = body.get('employeeId')
        employee_email = body.get('employeeEmail')
        employee_name = body.get('employeeName')
        template_id = body.get('templateId')
        
        # Validate required fields
        if not all([company_id, employee_id, employee_email, template_id]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required fields',
                    'required': ['companyId', 'employeeId', 'employeeEmail', 'templateId']
                })
            }
        
        # Validate template exists
        if template_id not in TEMPLATES:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Invalid template ID: {template_id}',
                    'availableTemplates': list(TEMPLATES.keys())
                })
            }
        
        # Generate unique tracking ID
        tracking_id = f"track_{uuid.uuid4().hex[:16]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Create tracking record in DynamoDB
        tracking_table = dynamodb.Table(EMAIL_TRACKING_TABLE)
        tracking_table.put_item(
            Item={
                'trackingId': tracking_id,
                'companyId': company_id,
                'employeeId': employee_id,
                'employeeName': employee_name,
                'employeeEmail': employee_email,
                'templateId': template_id,
                'emailSentAt': timestamp,
                'isOpened': False,
                'openedAt': None,
                'scamClicks': []
            }
        )
        
        # Generate phishing URL with tracking ID
        phishing_url = f"https://{CLOUDFRONT_DOMAIN}/templates/{template_id}.html?tid={tracking_id}"
        
        # Get template metadata
        template_meta = TEMPLATES[template_id]
        
        # Compose email
        email_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2>Security Alert / Important Notice</h2>
        <p>Dear {employee_name},</p>
        <p>We detected unusual activity on your account. Please verify your information immediately.</p>
        <p style="margin: 30px 0;">
            <a href="{phishing_url}" 
               style="background: #dc3545; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Verify Now
            </a>
        </p>
        <p style="color: #666; font-size: 12px;">If you did not request this, please contact us immediately.</p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        <p style="color: #999; font-size: 11px;">
            This is a phishing simulation from ThinkBeforeClick for security awareness training.<br>
            No real action is required. Click the link to learn how to identify phishing attacks.
        </p>
    </div>
</body>
</html>
"""
        
        # Send email via SES
        response = ses.send_email(
            Source=f"{template_meta['from_name']} <{SENDER_EMAIL}>",
            Destination={
                'ToAddresses': [employee_email]
            },
            Message={
                'Subject': {
                    'Data': template_meta['subject'],
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': email_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        # Update employee record (increment sent count)
        employees_table = dynamodb.Table(EMPLOYEES_TABLE)
        employees_table.update_item(
            Key={'employeeId': employee_id},
            UpdateExpression='ADD sentEmails :inc',
            ExpressionAttributeValues={':inc': 1}
        )
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Phishing email sent successfully',
                'trackingId': tracking_id,
                'employeeEmail': employee_email,
                'templateId': template_id,
                'phishingUrl': phishing_url,
                'sesMessageId': response['MessageId']
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


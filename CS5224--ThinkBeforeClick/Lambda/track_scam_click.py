"""
Lambda Function: Track Scam Click
Triggers: API Gateway POST /api/track-click

This function tracks when an employee clicks on a scam link in the phishing template.
"""

import json
import boto3
from datetime import datetime
from decimal import Decimal
import os

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
EMAIL_TRACKING_TABLE = os.environ.get('EMAIL_TRACKING_TABLE', 'ThinkBeforeClick-EmailTracking')
SCAM_CLICKS_TABLE = os.environ.get('SCAM_CLICKS_TABLE', 'ThinkBeforeClick-ScamClicks')
EMPLOYEES_TABLE = os.environ.get('EMPLOYEES_TABLE', 'ThinkBeforeClick-Employees')

# Custom JSON encoder to handle Decimal types from DynamoDB
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert Decimal to int if it's a whole number, otherwise to float
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Track scam click event
    
    Expected input:
    {
        "trackingId": "track_abc123def456",
        "scamType": "scam1"
    }
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        tracking_id = body.get('trackingId')
        scam_type = body.get('scamType')
        
        if not all([tracking_id, scam_type]):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required fields',
                    'required': ['trackingId', 'scamType']
                })
            }
        
        # Get tracking record from DynamoDB
        tracking_table = dynamodb.Table(EMAIL_TRACKING_TABLE)
        response = tracking_table.get_item(
            Key={'trackingId': tracking_id}
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Tracking ID not found'
                })
            }
        
        tracking_record = response['Item']
        timestamp = datetime.utcnow().isoformat()
        click_id = f"click_{tracking_id}_{scam_type}_{int(datetime.utcnow().timestamp())}"
        
        # Create scam click record
        scam_clicks_table = dynamodb.Table(SCAM_CLICKS_TABLE)
        scam_clicks_table.put_item(
            Item={
                'clickId': click_id,
                'trackingId': tracking_id,
                'companyId': tracking_record['companyId'],
                'employeeId': tracking_record['employeeId'],
                'employeeName': tracking_record.get('employeeName', 'Unknown'),
                'templateId': tracking_record['templateId'],
                'scamType': scam_type,
                'clickedAt': timestamp
            }
        )
        
        # Update tracking record with scam click
        tracking_table.update_item(
            Key={'trackingId': tracking_id},
            UpdateExpression='SET scamClicks = list_append(if_not_exists(scamClicks, :empty_list), :new_click)',
            ExpressionAttributeValues={
                ':empty_list': [],
                ':new_click': [{
                    'scamType': scam_type,
                    'clickedAt': timestamp
                }]
            }
        )
        
        # Update employee statistics
        employees_table = dynamodb.Table(EMPLOYEES_TABLE)
        employees_table.update_item(
            Key={'employeeId': tracking_record['employeeId']},
            UpdateExpression='ADD clickedScams :inc',
            ExpressionAttributeValues={':inc': 1}
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Scam click tracked successfully',
                'clickId': click_id,
                'trackingId': tracking_id,
                'scamType': scam_type,
                'clickedAt': timestamp
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


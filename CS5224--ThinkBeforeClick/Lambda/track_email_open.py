"""
Lambda Function: Track Email Open
Triggers: API Gateway GET /api/track-open/{trackingId}

This function tracks when an employee opens a phishing email.
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
    Track email open event
    
    Path parameters:
    {
        "trackingId": "track_abc123def456"
    }
    """
    try:
        # Get tracking ID from path parameters
        tracking_id = event.get('pathParameters', {}).get('trackingId')
        
        if not tracking_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing tracking ID'
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
        
        # Only update if not already opened (track first open only)
        if not tracking_record.get('isOpened', False):
            timestamp = datetime.utcnow().isoformat()
            
            # Update tracking record
            tracking_table.update_item(
                Key={'trackingId': tracking_id},
                UpdateExpression='SET isOpened = :opened, openedAt = :timestamp',
                ExpressionAttributeValues={
                    ':opened': True,
                    ':timestamp': timestamp
                }
            )
            
            # Update employee statistics
            employees_table = dynamodb.Table(EMPLOYEES_TABLE)
            employees_table.update_item(
                Key={'employeeId': tracking_record['employeeId']},
                UpdateExpression='ADD openedEmails :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Email open tracked successfully',
                    'trackingId': tracking_id,
                    'openedAt': timestamp,
                    'firstOpen': True
                })
            }
        else:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'message': 'Email was already opened',
                    'trackingId': tracking_id,
                    'openedAt': tracking_record.get('openedAt'),
                    'firstOpen': False
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


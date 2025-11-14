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


dynamodb = boto3.resource('dynamodb')

EMAIL_TRACKING_TABLE = os.environ.get('EMAIL_TRACKING_TABLE', 'ThinkBeforeClick-EmailTracking')
EMPLOYEES_TABLE = os.environ.get('EMPLOYEES_TABLE', 'ThinkBeforeClick-Employees')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
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

        if not tracking_record.get('isOpened', False):
            timestamp = datetime.utcnow().isoformat()

            tracking_table.update_item(
                Key={'trackingId': tracking_id},
                UpdateExpression='SET isOpened = :opened, openedAt = :timestamp',
                ExpressionAttributeValues={
                    ':opened': True,
                    ':timestamp': timestamp
                }
            )

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


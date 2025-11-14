"""
Lambda Function: Get Employees
Triggers: API Gateway GET /api/employees/{companyId}

This function retrieves all employees for a specific company.
"""

import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import os

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
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
    Get all employees for a company
    
    Path parameters:
    {
        "companyId": "company-123"
    }
    """
    try:
        # Get company ID from path parameters
        company_id = event.get('pathParameters', {}).get('companyId')
        
        if not company_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing company ID'
                })
            }
        
        # Query employees from DynamoDB
        employees_table = dynamodb.Table(EMPLOYEES_TABLE)
        
        # Try using GSI if it exists, otherwise scan
        try:
            response = employees_table.query(
                IndexName='CompanyIndex',
                KeyConditionExpression=Key('companyId').eq(company_id)
            )
        except:
            # Fallback to scan if GSI doesn't exist
            response = employees_table.scan(
                FilterExpression='companyId = :company',
                ExpressionAttributeValues={
                    ':company': company_id
                }
            )
        
        employees = response.get('Items', [])
        
        # Sort employees by addedAt (newest first)
        employees.sort(key=lambda x: x.get('addedAt', ''), reverse=True)
        
        # Return employee list
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'companyId': company_id,
                'totalEmployees': len(employees),
                'employees': employees
            }, cls=DecimalEncoder)
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


"""
Lambda Function: Generate Company Report
Triggers: API Gateway GET /api/company-report/{companyId}

This function generates comprehensive analytics for a company's phishing simulations.
"""

import json
import boto3
from boto3.dynamodb.conditions import Key
from collections import defaultdict
from decimal import Decimal
import os


dynamodb = boto3.resource('dynamodb')


EMAIL_TRACKING_TABLE = os.environ.get('EMAIL_TRACKING_TABLE', 'ThinkBeforeClick-EmailTracking')
SCAM_CLICKS_TABLE = os.environ.get('SCAM_CLICKS_TABLE', 'ThinkBeforeClick-ScamClicks')
EMPLOYEES_TABLE = os.environ.get('EMPLOYEES_TABLE', 'ThinkBeforeClick-Employees')


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Generate company analytics report
    
    Path parameters:
    {
        "companyId": "company-123"
    }
    """
    try:
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

        tracking_table = dynamodb.Table(EMAIL_TRACKING_TABLE)
        tracking_response = tracking_table.query(
            IndexName='CompanyIndex',
            KeyConditionExpression=Key('companyId').eq(company_id)
        )
        
        tracking_records = tracking_response.get('Items', [])

        scam_clicks_table = dynamodb.Table(SCAM_CLICKS_TABLE)
        clicks_response = scam_clicks_table.query(
            IndexName='CompanyIndex',
            KeyConditionExpression=Key('companyId').eq(company_id)
        )
        
        scam_clicks = clicks_response.get('Items', [])

        employees_table = dynamodb.Table(EMPLOYEES_TABLE)
        try:
            employees_response = employees_table.query(
                IndexName='CompanyIndex',
                KeyConditionExpression=Key('companyId').eq(company_id)
            )
        except:
            employees_response = employees_table.scan(
                FilterExpression='companyId = :company',
                ExpressionAttributeValues={
                    ':company': company_id
                }
            )
        
        employees = employees_response.get('Items', [])

        total_simulations = len(tracking_records)
        opened_count = sum(1 for record in tracking_records if record.get('isOpened', False))
        open_rate = round((opened_count / total_simulations * 100), 2) if total_simulations > 0 else 0

        employee_ranking = [
            {
                'employeeId': emp.get('employeeId'),
                'name': emp.get('name', 'Unknown'),
                'email': emp.get('email', 'Unknown'),
                'sentEmails': emp.get('sentEmails', 0),
                'openedEmails': emp.get('openedEmails', 0),
                'clickedScams': emp.get('clickedScams', 0),
                'addedAt': emp.get('addedAt', '')
            }
            for emp in employees
        ]

        employee_ranking.sort(key=lambda x: (x['clickedScams'], x['openedEmails'], x['sentEmails']), reverse=True)

        tracking_with_clicks = sum(1 for record in tracking_records if record.get('scamClicks') and len(record.get('scamClicks', [])) > 0)
        click_rate = round((tracking_with_clicks / total_simulations * 100), 2) if total_simulations > 0 else 0

        scam_type_counts = defaultdict(int)
        for click in scam_clicks:
            scam_type_counts[click['scamType']] += 1

        most_clicked_scams = [
            {'scamType': scam_type, 'clickCount': count}
            for scam_type, count in scam_type_counts.items()
        ]
        most_clicked_scams.sort(key=lambda x: x['clickCount'], reverse=True)

        template_stats = defaultdict(lambda: {'total': 0, 'opened': 0, 'clicked': 0})
        for record in tracking_records:
            template_id = record['templateId']
            template_stats[template_id]['total'] += 1
            if record.get('isOpened', False):
                template_stats[template_id]['opened'] += 1
            if record.get('scamClicks') and len(record.get('scamClicks', [])) > 0:
                template_stats[template_id]['clicked'] += 1
        
        template_performance = [
            {
                'templateId': template_id,
                'total': stats['total'],
                'openRate': round((stats['opened'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0,
                'clickRate': round((stats['clicked'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0
            }
            for template_id, stats in template_stats.items()
        ]

        report = {
            'companyId': company_id,
            'summary': {
                'totalSimulations': total_simulations,
                'openedCount': opened_count,
                'openRate': open_rate,
                'clickRate': click_rate,
                'totalScamClicks': len(scam_clicks)
            },
            'employeeRanking': employee_ranking,
            'mostClickedScams': most_clicked_scams,
            'templatePerformance': template_performance,
            'generatedAt': boto3.client('sts').get_caller_identity()['Account']  
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(report, cls=DecimalEncoder)
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


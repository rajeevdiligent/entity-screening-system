#!/usr/bin/env python3
"""
Production Monitoring and Health Check Components
"""

import json
import time
import boto3
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CloudWatchMetrics:
    """Custom CloudWatch metrics for business logic monitoring"""
    
    def __init__(self, namespace: str = 'SearchAgent'):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = namespace
    
    def put_metric(self, metric_name: str, value: float, unit: str = 'Count',
                   dimensions: Dict[str, str] = None):
        """Put custom metric to CloudWatch"""
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            
        except Exception as e:
            logger.error(f"Failed to put metric {metric_name}: {e}")
    
    def record_search_metrics(self, query: str, results_count: int, 
                            processing_time: float, success: bool):
        """Record search-specific metrics"""
        dimensions = {
            'Service': 'SearchService',
            'Status': 'Success' if success else 'Error'
        }
        
        self.put_metric('SearchRequests', 1, 'Count', dimensions)
        self.put_metric('SearchResultsCount', results_count, 'Count', dimensions)
        self.put_metric('SearchProcessingTime', processing_time, 'Seconds', dimensions)
    
    def record_llm_metrics(self, query: str, processing_time: float, 
                          relevance_score: float, success: bool):
        """Record LLM processing metrics"""
        dimensions = {
            'Service': 'LLMService',
            'Status': 'Success' if success else 'Error'
        }
        
        self.put_metric('LLMRequests', 1, 'Count', dimensions)
        self.put_metric('LLMProcessingTime', processing_time, 'Seconds', dimensions)
        if success:
            self.put_metric('LLMRelevanceScore', relevance_score, 'None', dimensions)
    
    def increment_counter(self, metric_name: str, dimensions: Dict[str, str] = None):
        """Increment a counter metric by 1"""
        self.put_metric(metric_name, 1, 'Count', dimensions)
    
    def record_custom_metric(self, metric_name: str, value: float, unit: str = 'Count', dimensions: Dict[str, str] = None):
        """Record a custom metric with specified value and unit"""
        self.put_metric(metric_name, value, unit, dimensions)

class HealthChecker:
    """Health check implementation for Lambda functions"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.bedrock = boto3.client('bedrock-runtime')
        self.sns = boto3.client('sns')
    
    def check_dynamodb_health(self, table_name: str) -> Dict[str, Any]:
        """Check DynamoDB table health"""
        try:
            table = self.dynamodb.Table(table_name)
            response = table.describe_table()
            
            status = response['Table']['TableStatus']
            
            return {
                'service': 'DynamoDB',
                'status': 'healthy' if status == 'ACTIVE' else 'unhealthy',
                'details': {
                    'table_status': status,
                    'item_count': response['Table'].get('ItemCount', 0)
                }
            }
            
        except Exception as e:
            return {
                'service': 'DynamoDB',
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_bedrock_health(self) -> Dict[str, Any]:
        """Check Bedrock service health"""
        try:
            # Simple test call to Bedrock
            test_prompt = "Test"
            model_id = "amazon.nova-micro-v1:0"
            
            body = json.dumps({
                "inputText": test_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 10,
                    "temperature": 0.1
                }
            })
            
            start_time = time.time()
            response = self.bedrock.invoke_model(
                body=body,
                modelId=model_id,
                accept="application/json",
                contentType="application/json"
            )
            response_time = time.time() - start_time
            
            return {
                'service': 'Bedrock',
                'status': 'healthy',
                'details': {
                    'response_time': response_time,
                    'model_id': model_id
                }
            }
            
        except Exception as e:
            return {
                'service': 'Bedrock',
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_sns_health(self, topic_arn: str) -> Dict[str, Any]:
        """Check SNS topic health"""
        try:
            response = self.sns.get_topic_attributes(TopicArn=topic_arn)
            
            return {
                'service': 'SNS',
                'status': 'healthy',
                'details': {
                    'topic_arn': topic_arn,
                    'subscriptions_confirmed': response['Attributes'].get('SubscriptionsConfirmed', '0')
                }
            }
            
        except Exception as e:
            return {
                'service': 'SNS',
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def comprehensive_health_check(self, table_name: str, topic_arn: str) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_checks = [
            self.check_dynamodb_health(table_name),
            self.check_bedrock_health(),
            self.check_sns_health(topic_arn)
        ]
        
        overall_status = 'healthy' if all(
            check['status'] == 'healthy' for check in health_checks
        ) else 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': health_checks
        }

def health_check_lambda_handler(event, context):
    """Lambda handler for health checks"""
    
    try:
        health_checker = HealthChecker()
        
        table_name = os.environ.get('RESULTS_TABLE', 'search-analysis-results')
        topic_arn = os.environ.get('LLM_PROCESSING_TOPIC', '')
        
        health_status = health_checker.comprehensive_health_check(table_name, topic_arn)
        
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache'
            },
            'body': json.dumps(health_status, default=str)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'overall_status': 'unhealthy',
                'error': 'Health check system failure',
                'timestamp': datetime.utcnow().isoformat()
            })
        }

class PerformanceMonitor:
    """Performance monitoring and alerting"""
    
    def __init__(self):
        self.metrics = CloudWatchMetrics()
    
    def monitor_function_performance(self, function_name: str):
        """Decorator to monitor Lambda function performance"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = False
                error = None
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:
                    error = str(e)
                    raise
                finally:
                    processing_time = time.time() - start_time
                    
                    # Record performance metrics
                    dimensions = {
                        'FunctionName': function_name,
                        'Status': 'Success' if success else 'Error'
                    }
                    
                    self.metrics.put_metric('FunctionInvocations', 1, 'Count', dimensions)
                    self.metrics.put_metric('FunctionDuration', processing_time, 'Seconds', dimensions)
                    
                    if error:
                        self.metrics.put_metric('FunctionErrors', 1, 'Count', dimensions)
            
            return wrapper
        return decorator

# Example usage:
# performance_monitor = PerformanceMonitor()
# 
# @performance_monitor.monitor_function_performance('search-service')
# def lambda_handler(event, context):
#     # Your Lambda function code here
#     pass

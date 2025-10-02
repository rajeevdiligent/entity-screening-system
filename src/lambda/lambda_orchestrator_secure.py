#!/usr/bin/env python3
"""
Production-Ready Orchestrator Lambda
Central coordinator with security, monitoring, and error handling
"""

import json
import os
import boto3
from typing import Dict, Any
from datetime import datetime
import logging

# Import production components
from shared.production_security_fixes import SecurityManager, InputValidator, create_secure_response
from shared.production_monitoring import CloudWatchMetrics, PerformanceMonitor
from shared.dynamodb_data_service import SearchResultsDataService

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize monitoring
metrics = CloudWatchMetrics()
performance_monitor = PerformanceMonitor()

@performance_monitor.monitor_function_performance('orchestrator-service')
def lambda_handler(event, context):
    """
    Production-ready orchestrator Lambda handler
    
    Routes requests to appropriate services based on processing mode:
    - 'search_only': Just perform search
    - 'async': Search + async LLM processing via SNS
    - 'sync': Search + sync LLM processing via Step Functions
    """
    
    start_time = datetime.now()
    
    try:
        # Initialize services
        validator = InputValidator()
        
        # Handle different event sources
        if 'httpMethod' in event:
            # API Gateway request
            return handle_api_gateway_request(event, context)
        elif 'Records' in event:
            # SNS/SQS triggered
            return handle_event_driven_request(event, context)
        else:
            # Direct invocation
            return handle_direct_invocation(event, context)
            
    except Exception as e:
        logger.error(f"Unexpected error in orchestrator: {str(e)}")
        metrics.put_metric('OrchestratorErrors', 1, 'Count', {'Service': 'Orchestrator'})
        return create_secure_response(500, {'error': 'Internal server error'})

def handle_api_gateway_request(event: Dict, context: Any) -> Dict:
    """Handle API Gateway requests"""
    
    try:
        # Extract request data
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '')
        query_params = event.get('queryStringParameters') or {}
        
        # Parse request body
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except json.JSONDecodeError:
                return create_secure_response(400, {'error': 'Invalid JSON in request body'})
        
        # Route based on path and method
        if http_method == 'POST' and '/search' in path:
            return handle_search_request(body, event)
        elif http_method == 'GET' and '/health' in path:
            return handle_health_check()
        else:
            return create_secure_response(404, {'error': 'Endpoint not found'})
            
    except Exception as e:
        logger.error(f"API Gateway request handling failed: {e}")
        return create_secure_response(500, {'error': 'Request processing failed'})

def handle_search_request(body: Dict, event: Dict) -> Dict:
    """Handle search requests with validation and routing"""
    
    try:
        # Initialize services
        validator = InputValidator()
        lambda_client = boto3.client('lambda')
        
        # Check for entity screening mode
        use_entity_screening = body.get('use_entity_screening', False)
        entity_name = body.get('entity_name', '')
        
        # Validate input
        try:
            if use_entity_screening and entity_name:
                # For entity screening, entity_name is the primary input
                entity_name = validator.validate_search_query(entity_name)
                query = entity_name  # Use entity name as query for compatibility
            else:
                query = validator.validate_search_query(body.get('query', ''))
            
            num_results = validator.validate_num_results(body.get('num_results', 10))
            processing_mode = body.get('processing_mode', 'search_only')
        except ValueError as e:
            logger.warning(f"Input validation failed: {e}")
            return create_secure_response(400, {'error': str(e)})
        
        # Validate processing mode
        valid_modes = ['search_only', 'async', 'sync']
        if processing_mode not in valid_modes:
            return create_secure_response(400, {
                'error': f'Invalid processing_mode. Must be one of: {valid_modes}'
            })
        
        # Get client information for tracking
        client_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        request_id = event.get('requestContext', {}).get('requestId', 'unknown')
        
        # Route based on processing mode and screening type
        if use_entity_screening:
            # Use entity screening service for comprehensive screening
            return handle_entity_screening_workflow(body, client_ip, request_id)
        elif processing_mode == 'search_only':
            return handle_search_only(query, num_results, client_ip, request_id)
        elif processing_mode == 'async':
            return handle_async_workflow(query, num_results, client_ip, request_id)
        elif processing_mode == 'sync':
            return handle_sync_workflow(query, num_results, client_ip, request_id)
            
    except Exception as e:
        logger.error(f"Search request handling failed: {e}")
        return create_secure_response(500, {'error': 'Search processing failed'})

def handle_search_only(query: str, num_results: int, client_ip: str, request_id: str) -> Dict:
    """Handle search-only requests"""
    
    try:
        lambda_client = boto3.client('lambda')
        
        # Invoke search service
        search_payload = {
            'query': query,
            'num_results': num_results,
            'store_results': True,
            'process_with_llm': False,
            'client_info': {
                'ip': client_ip,
                'request_id': request_id
            }
        }
        
        response = lambda_client.invoke(
            FunctionName=os.getenv('SEARCH_FUNCTION_NAME', 'search-service'),
            InvocationType='RequestResponse',
            Payload=json.dumps(search_payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        if response.get('StatusCode') == 200:
            # Record success metrics
            metrics.put_metric('SearchOnlyRequests', 1, 'Count', {
                'Status': 'Success',
                'ProcessingMode': 'search_only'
            })
            
            return create_secure_response(200, {
                'success': True,
                'processing_mode': 'search_only',
                'data': json.loads(response_payload.get('body', '{}'))
            })
        else:
            logger.error(f"Search service failed: {response_payload}")
            metrics.put_metric('SearchOnlyRequests', 1, 'Count', {
                'Status': 'Error',
                'ProcessingMode': 'search_only'
            })
            return create_secure_response(500, {'error': 'Search service failed'})
            
    except Exception as e:
        logger.error(f"Search-only processing failed: {e}")
        metrics.put_metric('SearchOnlyRequests', 1, 'Count', {
            'Status': 'Error',
            'ProcessingMode': 'search_only'
        })
        return create_secure_response(500, {'error': 'Search processing failed'})

def handle_async_workflow(query: str, num_results: int, client_ip: str, request_id: str) -> Dict:
    """Handle asynchronous workflow with SNS"""
    
    try:
        lambda_client = boto3.client('lambda')
        
        # Invoke search service with LLM processing trigger
        search_payload = {
            'query': query,
            'num_results': num_results,
            'store_results': True,
            'process_with_llm': True,
            'callback_topic': os.getenv('LLM_PROCESSING_TOPIC'),
            'client_info': {
                'ip': client_ip,
                'request_id': request_id
            }
        }
        
        response = lambda_client.invoke(
            FunctionName=os.getenv('SEARCH_FUNCTION_NAME', 'search-service'),
            InvocationType='RequestResponse',
            Payload=json.dumps(search_payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        
        if response.get('StatusCode') == 200:
            metrics.put_metric('AsyncRequests', 1, 'Count', {
                'Status': 'Success',
                'ProcessingMode': 'async'
            })
            
            search_data = json.loads(response_payload.get('body', '{}'))
            
            return create_secure_response(202, {
                'success': True,
                'processing_mode': 'async',
                'message': 'Search completed, LLM analysis in progress',
                'search_results': search_data.get('results', []),
                'tracking': {
                    'query_hash': search_data.get('storage_info', {}).get('query_hash'),
                    'timestamp': search_data.get('timestamp'),
                    'request_id': request_id
                }
            })
        else:
            logger.error(f"Async workflow failed: {response_payload}")
            metrics.put_metric('AsyncRequests', 1, 'Count', {
                'Status': 'Error',
                'ProcessingMode': 'async'
            })
            return create_secure_response(500, {'error': 'Async workflow failed'})
            
    except Exception as e:
        logger.error(f"Async workflow processing failed: {e}")
        metrics.put_metric('AsyncRequests', 1, 'Count', {
            'Status': 'Error',
            'ProcessingMode': 'async'
        })
        return create_secure_response(500, {'error': 'Async processing failed'})

def handle_sync_workflow(query: str, num_results: int, client_ip: str, request_id: str) -> Dict:
    """Handle synchronous workflow with Step Functions"""
    
    try:
        stepfunctions = boto3.client('stepfunctions')
        
        # Start Step Functions execution
        workflow_input = {
            'query': query,
            'num_results': num_results,
            'client_info': {
                'ip': client_ip,
                'request_id': request_id
            },
            'timestamp': datetime.now().isoformat()
        }
        
        execution_name = f"search-analysis-{int(datetime.now().timestamp())}-{request_id[:8]}"
        
        response = stepfunctions.start_execution(
            stateMachineArn=os.getenv('STEP_FUNCTION_ARN'),
            name=execution_name,
            input=json.dumps(workflow_input)
        )
        
        # Wait for execution to complete (with timeout)
        execution_arn = response['executionArn']
        
        # Poll for completion (simplified - in production, consider async polling)
        import time
        max_wait_time = 60  # 60 seconds max wait
        poll_interval = 2   # Poll every 2 seconds
        waited_time = 0
        
        while waited_time < max_wait_time:
            execution_status = stepfunctions.describe_execution(executionArn=execution_arn)
            status = execution_status['status']
            
            if status == 'SUCCEEDED':
                # Get the output
                output = json.loads(execution_status.get('output', '{}'))
                
                metrics.put_metric('SyncRequests', 1, 'Count', {
                    'Status': 'Success',
                    'ProcessingMode': 'sync'
                })
                
                return create_secure_response(200, {
                    'success': True,
                    'processing_mode': 'sync',
                    'data': output,
                    'execution_arn': execution_arn
                })
            elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                logger.error(f"Step Functions execution failed: {status}")
                metrics.put_metric('SyncRequests', 1, 'Count', {
                    'Status': 'Error',
                    'ProcessingMode': 'sync'
                })
                return create_secure_response(500, {
                    'error': f'Workflow execution {status.lower()}',
                    'execution_arn': execution_arn
                })
            
            time.sleep(poll_interval)
            waited_time += poll_interval
        
        # Timeout reached
        logger.warning(f"Step Functions execution timeout: {execution_arn}")
        metrics.put_metric('SyncRequests', 1, 'Count', {
            'Status': 'Timeout',
            'ProcessingMode': 'sync'
        })
        
        return create_secure_response(202, {
            'success': False,
            'processing_mode': 'sync',
            'message': 'Processing timeout, execution continues in background',
            'execution_arn': execution_arn
        })
        
    except Exception as e:
        logger.error(f"Sync workflow processing failed: {e}")
        metrics.put_metric('SyncRequests', 1, 'Count', {
            'Status': 'Error',
            'ProcessingMode': 'sync'
        })
        return create_secure_response(500, {'error': 'Sync processing failed'})

def handle_entity_screening_workflow(body: Dict, client_ip: str, request_id: str) -> Dict:
    """Handle entity screening workflow using dedicated screening service"""
    
    try:
        lambda_client = boto3.client('lambda')
        
        # Prepare payload for entity screening service
        screening_payload = {
            'entity_name': body.get('entity_name'),
            'screening_categories': body.get('screening_categories', ['all']),
            'queries_per_category': body.get('queries_per_category', 5),
            'comprehensive_screening': body.get('comprehensive_screening', True),
            'store_results': body.get('store_results', True),
            'process_with_llm': body.get('process_with_llm', False),
            'callback_topic': body.get('callback_topic') or os.getenv('LLM_PROCESSING_TOPIC'),
            'client_info': {
                'ip': client_ip,
                'request_id': request_id
            }
        }
        
        # Invoke entity screening service
        response = lambda_client.invoke(
            FunctionName=os.getenv('ENTITY_SCREENING_FUNCTION_NAME', 'entity-screening-service'),
            InvocationType='RequestResponse',
            Payload=json.dumps(screening_payload)
        )
        
        response_payload = json.loads(response['Payload'].read())
        
        if response.get('StatusCode') == 200:
            metrics.put_metric('EntityScreeningRequests', 1, 'Count', {
                'Status': 'Success',
                'ProcessingMode': 'entity_screening'
            })
            
            screening_data = json.loads(response_payload.get('body', '{}'))
            
            return create_secure_response(200, {
                'success': True,
                'processing_mode': 'entity_screening',
                'entity_name': body.get('entity_name'),
                'screening_data': screening_data,
                'tracking': {
                    'request_id': request_id,
                    'timestamp': datetime.now().isoformat()
                }
            })
        else:
            logger.error(f"Entity screening service failed: {response_payload}")
            metrics.put_metric('EntityScreeningRequests', 1, 'Count', {
                'Status': 'Error',
                'ProcessingMode': 'entity_screening'
            })
            return create_secure_response(500, {'error': 'Entity screening service failed'})
            
    except Exception as e:
        logger.error(f"Entity screening workflow failed: {e}")
        metrics.put_metric('EntityScreeningRequests', 1, 'Count', {
            'Status': 'Error',
            'ProcessingMode': 'entity_screening'
        })
        return create_secure_response(500, {'error': 'Entity screening processing failed'})

def handle_health_check() -> Dict:
    """Handle health check requests"""
    
    try:
        health_status = {
            'service': 'orchestrator',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'dependencies': {}
        }
        
        # Check downstream services
        lambda_client = boto3.client('lambda')
        
        # Check search service
        try:
            lambda_client.get_function(FunctionName=os.getenv('SEARCH_FUNCTION_NAME', 'search-service'))
            health_status['dependencies']['search_service'] = 'healthy'
        except:
            health_status['dependencies']['search_service'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        # Check LLM service
        try:
            lambda_client.get_function(FunctionName=os.getenv('LLM_FUNCTION_NAME', 'llm-analysis-service'))
            health_status['dependencies']['llm_service'] = 'healthy'
        except:
            health_status['dependencies']['llm_service'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        # Check DynamoDB
        try:
            data_service = SearchResultsDataService()
            health_status['dependencies']['dynamodb'] = 'healthy'
        except:
            health_status['dependencies']['dynamodb'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return create_secure_response(status_code, health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_secure_response(500, {
            'service': 'orchestrator',
            'status': 'unhealthy',
            'error': 'Health check system failure',
            'timestamp': datetime.now().isoformat()
        })

def handle_event_driven_request(event: Dict, context: Any) -> Dict:
    """Handle SNS/SQS triggered requests"""
    
    try:
        # Process each record
        for record in event['Records']:
            if 'Sns' in record:
                # SNS message
                message = json.loads(record['Sns']['Message'])
                logger.info(f"Processing SNS message: {message.get('subject', 'No subject')}")
            elif 'body' in record:
                # SQS message
                message = json.loads(record['body'])
                logger.info(f"Processing SQS message")
            
            # Process the message (implement based on your needs)
            # This could trigger additional workflows or notifications
        
        return {'statusCode': 200, 'body': json.dumps({'message': 'Event processed successfully'})}
        
    except Exception as e:
        logger.error(f"Event-driven request processing failed: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Event processing failed'})}

def handle_direct_invocation(event: Dict, context: Any) -> Dict:
    """Handle direct Lambda invocations"""
    
    try:
        # Extract processing mode and route accordingly
        processing_mode = event.get('processing_mode', 'search_only')
        
        if processing_mode == 'search_only':
            return handle_search_only(
                event.get('query', ''),
                event.get('num_results', 10),
                'direct-invocation',
                context.aws_request_id
            )
        elif processing_mode == 'async':
            return handle_async_workflow(
                event.get('query', ''),
                event.get('num_results', 10),
                'direct-invocation',
                context.aws_request_id
            )
        elif processing_mode == 'sync':
            return handle_sync_workflow(
                event.get('query', ''),
                event.get('num_results', 10),
                'direct-invocation',
                context.aws_request_id
            )
        else:
            return create_secure_response(400, {'error': 'Invalid processing_mode'})
            
    except Exception as e:
        logger.error(f"Direct invocation processing failed: {e}")
        return create_secure_response(500, {'error': 'Direct invocation failed'})

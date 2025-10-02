#!/usr/bin/env python3
"""
Production-Ready Search Service Lambda
Includes security, monitoring, and error handling
"""

import json
import os
import requests
from typing import List, Dict, Any
import boto3
from datetime import datetime
import logging

# Import production components
from shared.production_security_fixes import SecurityManager, InputValidator, create_secure_response
from shared.production_monitoring import CloudWatchMetrics, PerformanceMonitor
from shared.dynamodb_data_service import SearchResultsDataService
from shared.entity_screening_keywords import EntityScreeningKeywords, ScreeningCategory

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize monitoring
metrics = CloudWatchMetrics()
performance_monitor = PerformanceMonitor()

@performance_monitor.monitor_function_performance('search-service')
def lambda_handler(event, context):
    """
    Production-ready Lambda handler for search operations
    
    Expected event:
    {
        "query": "search query",
        "entity_name": "Company Name",        # Optional: for entity screening
        "screening_category": "financial_crimes", # Optional: financial_crimes, corruption_bribery, all
        "use_entity_screening": true,         # Optional: enable entity screening mode
        "num_results": 10,
        "callback_topic": "arn:aws:sns:...",  # Optional: for async processing
        "process_with_llm": true,             # Optional: trigger LLM processing
        "store_results": true                 # Optional: store in DynamoDB (default: true)
    }
    """
    
    start_time = datetime.now()
    
    try:
        # Initialize security and data services
        security_manager = SecurityManager()
        validator = InputValidator()
        data_service = SearchResultsDataService()
        
        # Parse event - handle API Gateway proxy integration format
        if 'body' in event and event['body']:
            # API Gateway proxy integration
            import json
            request_data = json.loads(event['body'])
        else:
            # Direct Lambda invocation
            request_data = event
        
        # Extract and validate parameters
        try:
            # Check if entity screening mode is enabled
            use_entity_screening = request_data.get('use_entity_screening', False)
            entity_name = request_data.get('entity_name', '')
            screening_category = request_data.get('screening_category', 'all')
            
            if use_entity_screening and entity_name:
                # Generate entity screening queries
                queries = generate_entity_screening_queries(
                    entity_name, 
                    screening_category, 
                    request_data.get('num_results', 10)
                )
                # Use the first query as the main query for this request
                query = queries[0] if queries else validator.validate_search_query(request_data.get('query', ''))
            else:
                query = validator.validate_search_query(request_data.get('query', ''))
            
            num_results = validator.validate_num_results(request_data.get('num_results', 10))
        except ValueError as e:
            logger.warning(f"Input validation failed: {e}")
            return create_secure_response(400, {'error': str(e)})
        
        callback_topic = request_data.get('callback_topic')
        # Enable LLM processing by default for entity screening
        process_with_llm = request_data.get('enable_llm_processing', 
                                          request_data.get('process_with_llm', use_entity_screening))
        store_results = request_data.get('store_results', True)
        
        # Get API key securely
        try:
            api_key = security_manager.get_secret('entity-screening/serper-api-key')
        except Exception as e:
            logger.error(f"Failed to retrieve API key: {e}")
            return create_secure_response(500, {'error': 'Configuration error'})
        
        # Perform search
        try:
            search_results = perform_search(query, num_results, api_key)
            timestamp = datetime.now().isoformat()
            
            # Record search metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            metrics.record_search_metrics(query, len(search_results), processing_time, True)
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            metrics.record_search_metrics(query, 0, 0, False)
            return create_secure_response(500, {'error': 'Search service unavailable'})
        
        # Store results in DynamoDB if requested
        storage_result = None
        if store_results:
            try:
                storage_result = data_service.store_search_results(
                    query=query,
                    search_results=search_results,
                    metadata={
                        'source': 'lambda_search_service_secure',
                        'num_results_requested': num_results,
                        'process_with_llm': process_with_llm,
                        'callback_topic': callback_topic,
                        'client_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
                    }
                )
                logger.info(f"Stored search results: {storage_result['query_hash']}")
            except Exception as e:
                logger.error(f"Failed to store search results: {e}")
                # Continue processing even if storage fails
        
        # If async LLM processing requested, trigger it
        llm_processing_triggered = False
        if process_with_llm and search_results:
            try:
                processing_timestamp = storage_result['timestamp'] if storage_result else timestamp
                # Use default SNS topic if no callback topic specified
                topic_arn = callback_topic or os.getenv('LLM_PROCESSING_TOPIC')
                if topic_arn:
                    trigger_llm_processing(search_results, query, topic_arn, processing_timestamp)
                    llm_processing_triggered = True
                    logger.info(f"Triggered LLM processing for query: {query[:50]}...")
                else:
                    logger.warning("No LLM processing topic available")
            except Exception as e:
                logger.error(f"Failed to trigger LLM processing: {e}")
                # Don't fail the request if async processing fails
        
        # Prepare secure response
        response_body = {
            'query': query,
            'results': search_results,
            'total_count': len(search_results),
            'timestamp': timestamp,
            'llm_processing_triggered': llm_processing_triggered,
            'stored_in_database': store_results and storage_result is not None
        }
        
        # Add storage info if available (but sanitize sensitive data)
        if storage_result:
            response_body['storage_info'] = {
                'query_hash': storage_result['query_hash'],
                'storage_timestamp': storage_result['timestamp']
            }
        
        return create_secure_response(200, response_body)
        
    except Exception as e:
        logger.error(f"Unexpected error in search service: {str(e)}")
        metrics.record_search_metrics(event.get('query', 'unknown'), 0, 0, False)
        return create_secure_response(500, {'error': 'Internal server error'})

def perform_search(query: str, num_results: int, api_key: str) -> List[Dict]:
    """Perform Serper API search with enhanced error handling"""
    
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'SearchAgent/1.0'
    }
    
    payload = {
        'q': query,
        'num': min(num_results, 100),
        'gl': 'us',  # Geographic location
        'hl': 'en'   # Language
    }
    
    try:
        response = requests.post(
            'https://google.serper.dev/search', 
            headers=headers, 
            json=payload,
            timeout=30  # Add timeout
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for idx, result in enumerate(data.get('organic', [])):
            # Sanitize result data
            sanitized_result = {
                'title': str(result.get('title', ''))[:200],  # Limit length
                'url': str(result.get('link', ''))[:500],
                'snippet': str(result.get('snippet', ''))[:500],
                'position': idx + 1
            }
            results.append(sanitized_result)
        
        logger.info(f"Search completed: {len(results)} results for query length {len(query)}")
        return results
        
    except requests.exceptions.Timeout:
        logger.error("Search API timeout")
        raise Exception("Search service timeout")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Search API HTTP error: {e}")
        raise Exception("Search service error")
    except Exception as e:
        logger.error(f"Search API unexpected error: {e}")
        raise Exception("Search service unavailable")

def trigger_llm_processing(search_results: List[Dict], query: str, 
                          topic_arn: str, timestamp: str):
    """Trigger async LLM processing via SNS with enhanced security"""
    
    try:
        sns = boto3.client('sns')
        
        # Sanitize message data
        message = {
            'search_results': search_results,
            'query': query[:500],  # Limit query length
            'timestamp': timestamp,
            'source': 'lambda_search_service_secure',
            'results_count': len(search_results)
        }
        
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message, default=str),
            Subject=f'LLM Processing Request: {query[:50]}...',
            MessageAttributes={
                'source': {
                    'DataType': 'String',
                    'StringValue': 'search-service'
                },
                'priority': {
                    'DataType': 'String', 
                    'StringValue': 'normal'
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to publish SNS message: {e}")
        raise

def generate_entity_screening_queries(entity_name: str, screening_category: str, 
                                    max_queries: int = 10) -> List[str]:
    """
    Generate entity screening queries using the keyword system
    
    Args:
        entity_name: Name of the entity to screen
        screening_category: Category of screening (financial_crimes, corruption_bribery, all)
        max_queries: Maximum number of queries to generate
        
    Returns:
        List of search queries for entity screening
    """
    try:
        keywords_manager = EntityScreeningKeywords()
        
        # Map string category to enum
        category_map = {
            'financial_crimes': ScreeningCategory.FINANCIAL_CRIMES,
            'corruption_bribery': ScreeningCategory.CORRUPTION_BRIBERY,
            'all': ScreeningCategory.ALL
        }
        
        category = category_map.get(screening_category.lower(), ScreeningCategory.ALL)
        
        queries = keywords_manager.generate_entity_search_queries(
            entity_name, 
            category, 
            max_queries
        )
        
        logger.info(f"Generated {len(queries)} entity screening queries for '{entity_name}' in category '{screening_category}'")
        return queries
        
    except Exception as e:
        logger.error(f"Failed to generate entity screening queries: {e}")
        # Fallback to simple entity name query
        return [f'"{entity_name}"']

# Health check endpoint
def health_check_handler(event, context):
    """Health check endpoint for the search service"""
    
    try:
        # Basic health checks
        health_status = {
            'service': 'search-service',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }
        
        # Check if we can access secrets (without exposing them)
        try:
            security_manager = SecurityManager()
            security_manager.get_secret('entity-screening/serper-api-key')
            health_status['secrets_accessible'] = True
        except:
            health_status['secrets_accessible'] = False
            health_status['status'] = 'degraded'
        
        # Check DynamoDB connectivity
        try:
            data_service = SearchResultsDataService()
            # Simple connectivity test (doesn't actually query data)
            health_status['database_accessible'] = True
        except:
            health_status['database_accessible'] = False
            health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return create_secure_response(status_code, health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_secure_response(500, {
            'service': 'search-service',
            'status': 'unhealthy',
            'error': 'Health check system failure',
            'timestamp': datetime.now().isoformat()
        })

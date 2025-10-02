#!/usr/bin/env python3
"""
Entity Screening Service Lambda
Specialized service for comprehensive entity screening using financial crimes and corruption keywords
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

@performance_monitor.monitor_function_performance('entity-screening-service')
def lambda_handler(event, context):
    """
    Lambda handler for comprehensive entity screening
    
    Expected event:
    {
        "entity_name": "Company Name",                    # Required: entity to screen
        "screening_categories": ["financial_crimes"],    # Optional: categories to screen
        "queries_per_category": 5,                       # Optional: queries per category
        "comprehensive_screening": true,                 # Optional: screen all categories
        "store_results": true,                          # Optional: store in DynamoDB
        "process_with_llm": true,                       # Optional: trigger LLM analysis
        "callback_topic": "arn:aws:sns:..."             # Optional: for async LLM processing
    }
    """
    
    start_time = datetime.now()
    
    try:
        # Initialize services
        security_manager = SecurityManager()
        validator = InputValidator()
        data_service = SearchResultsDataService()
        keywords_manager = EntityScreeningKeywords()
        
        # Extract and validate parameters
        entity_name = event.get('entity_name', '').strip()
        if not entity_name:
            return create_secure_response(400, {'error': 'entity_name is required'})
        
        # Validate entity name
        try:
            entity_name = validator.validate_search_query(entity_name)
        except ValueError as e:
            logger.warning(f"Entity name validation failed: {e}")
            return create_secure_response(400, {'error': f'Invalid entity name: {str(e)}'})
        
        screening_categories = event.get('screening_categories', ['all'])
        queries_per_category = event.get('queries_per_category', 5)
        comprehensive_screening = event.get('comprehensive_screening', False)
        store_results = event.get('store_results', True)
        process_with_llm = event.get('process_with_llm', False)
        callback_topic = event.get('callback_topic')
        
        # Get API key securely
        try:
            api_key = security_manager.get_secret('serper-api-key')
        except Exception as e:
            logger.error(f"Failed to retrieve API key: {e}")
            return create_secure_response(500, {'error': 'Configuration error'})
        
        # Perform comprehensive entity screening
        screening_results = perform_comprehensive_screening(
            entity_name,
            screening_categories,
            queries_per_category,
            comprehensive_screening,
            api_key
        )
        
        # Record metrics
        processing_time = (datetime.now() - start_time).total_seconds()
        total_results = sum(len(results) for results in screening_results.values())
        
        metrics.put_metric('EntityScreeningRequests', 1, 'Count', {
            'Status': 'Success',
            'EntityName': entity_name[:50]  # Truncate for privacy
        })
        metrics.put_metric('EntityScreeningResults', total_results, 'Count')
        metrics.put_metric('EntityScreeningTime', processing_time, 'Seconds')
        
        # Store results in DynamoDB if requested
        storage_results = {}
        if store_results:
            try:
                for category, results in screening_results.items():
                    if results:  # Only store if there are results
                        storage_result = data_service.store_search_results(
                            query=f"Entity Screening: {entity_name} - {category}",
                            search_results=results,
                            metadata={
                                'source': 'lambda_entity_screening_service',
                                'entity_name': entity_name,
                                'screening_category': category,
                                'screening_type': 'comprehensive' if comprehensive_screening else 'targeted',
                                'total_categories_screened': len(screening_results),
                                'client_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
                            }
                        )
                        storage_results[category] = storage_result
                        
                logger.info(f"Stored screening results for {len(storage_results)} categories")
            except Exception as e:
                logger.error(f"Failed to store screening results: {e}")
        
        # Trigger LLM processing if requested
        if process_with_llm and callback_topic and screening_results:
            try:
                # Combine all results for LLM processing
                all_results = []
                for category, results in screening_results.items():
                    all_results.extend(results)
                
                if all_results:
                    trigger_llm_processing(
                        all_results, 
                        f"Entity Screening: {entity_name}", 
                        callback_topic,
                        datetime.now().isoformat()
                    )
                    logger.info(f"Triggered LLM processing for {len(all_results)} screening results")
            except Exception as e:
                logger.error(f"Failed to trigger LLM processing: {e}")
        
        # Prepare response
        response_data = {
            'entity_name': entity_name,
            'screening_results': screening_results,
            'screening_summary': {
                'total_categories_screened': len(screening_results),
                'total_results_found': total_results,
                'categories_with_results': [cat for cat, results in screening_results.items() if results],
                'processing_time_seconds': processing_time
            },
            'timestamp': datetime.now().isoformat(),
            'stored_in_database': store_results and bool(storage_results),
            'llm_processing_triggered': process_with_llm and callback_topic is not None
        }
        
        # Add storage info if available
        if storage_results:
            response_data['storage_info'] = {
                category: {
                    'query_hash': result['query_hash'],
                    'timestamp': result['timestamp']
                }
                for category, result in storage_results.items()
            }
        
        return create_secure_response(200, response_data)
        
    except Exception as e:
        logger.error(f"Unexpected error in entity screening service: {str(e)}")
        metrics.put_metric('EntityScreeningErrors', 1, 'Count', {
            'ErrorType': type(e).__name__
        })
        return create_secure_response(500, {'error': 'Entity screening service error'})

def perform_comprehensive_screening(entity_name: str, screening_categories: List[str],
                                  queries_per_category: int, comprehensive_screening: bool,
                                  api_key: str) -> Dict[str, List[Dict]]:
    """
    Perform comprehensive entity screening across multiple categories
    
    Args:
        entity_name: Name of the entity to screen
        screening_categories: List of categories to screen
        queries_per_category: Number of queries per category
        comprehensive_screening: Whether to screen all categories
        api_key: Serper API key
        
    Returns:
        Dictionary with category names as keys and search results as values
    """
    keywords_manager = EntityScreeningKeywords()
    results = {}
    
    try:
        if comprehensive_screening:
            # Screen all categories comprehensively
            comprehensive_queries = keywords_manager.generate_comprehensive_search_queries(
                entity_name, queries_per_category
            )
            
            for category, queries in comprehensive_queries.items():
                category_results = []
                for query in queries:
                    try:
                        search_results = perform_single_search(query, 5, api_key)  # 5 results per query
                        category_results.extend(search_results)
                        
                        # Add small delay to avoid rate limiting
                        import time
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"Search failed for query '{query}': {e}")
                        continue
                
                results[category] = category_results
                logger.info(f"Found {len(category_results)} results for category '{category}'")
        
        else:
            # Screen specific categories
            category_map = {
                'financial_crimes': ScreeningCategory.FINANCIAL_CRIMES,
                'corruption_bribery': ScreeningCategory.CORRUPTION_BRIBERY,
                'all': ScreeningCategory.ALL
            }
            
            for category_name in screening_categories:
                category = category_map.get(category_name.lower(), ScreeningCategory.ALL)
                
                queries = keywords_manager.generate_entity_search_queries(
                    entity_name, category, queries_per_category
                )
                
                category_results = []
                for query in queries:
                    try:
                        search_results = perform_single_search(query, 3, api_key)  # 3 results per query
                        category_results.extend(search_results)
                        
                        # Add small delay to avoid rate limiting
                        import time
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.warning(f"Search failed for query '{query}': {e}")
                        continue
                
                results[category_name] = category_results
                logger.info(f"Found {len(category_results)} results for category '{category_name}'")
        
        return results
        
    except Exception as e:
        logger.error(f"Comprehensive screening failed: {e}")
        return {}

def perform_single_search(query: str, num_results: int, api_key: str) -> List[Dict]:
    """
    Perform a single search using Serper API
    
    Args:
        query: Search query
        num_results: Number of results to return
        api_key: Serper API key
        
    Returns:
        List of search results
    """
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'EntityScreeningAgent/1.0'
    }
    
    payload = {
        'q': query,
        'num': min(num_results, 10),
        'gl': 'us',
        'hl': 'en'
    }
    
    try:
        response = requests.post(
            'https://google.serper.dev/search',
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for idx, result in enumerate(data.get('organic', [])):
            sanitized_result = {
                'title': str(result.get('title', ''))[:200],
                'url': str(result.get('link', ''))[:500],
                'snippet': str(result.get('snippet', ''))[:500],
                'position': idx + 1,
                'search_query': query  # Include the query that found this result
            }
            results.append(sanitized_result)
        
        return results
        
    except requests.exceptions.Timeout:
        logger.error(f"Search timeout for query: {query}")
        raise Exception("Search timeout")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Search HTTP error for query '{query}': {e}")
        raise Exception("Search API error")
    except Exception as e:
        logger.error(f"Search error for query '{query}': {e}")
        raise Exception("Search failed")

def trigger_llm_processing(search_results: List[Dict], entity_query: str,
                          topic_arn: str, timestamp: str):
    """
    Trigger LLM processing for entity screening results
    
    Args:
        search_results: Combined search results from all categories
        entity_query: Entity screening query description
        topic_arn: SNS topic ARN for LLM processing
        timestamp: Processing timestamp
    """
    try:
        sns = boto3.client('sns')
        
        message = {
            'search_results': search_results,
            'query': entity_query,
            'timestamp': timestamp,
            'source': 'lambda_entity_screening_service',
            'screening_type': 'comprehensive_entity_screening',
            'results_count': len(search_results)
        }
        
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message, default=str),
            Subject=f'Entity Screening LLM Analysis: {entity_query[:50]}...',
            MessageAttributes={
                'source': {
                    'DataType': 'String',
                    'StringValue': 'entity-screening-service'
                },
                'priority': {
                    'DataType': 'String',
                    'StringValue': 'high'  # Entity screening gets high priority
                },
                'screening_type': {
                    'DataType': 'String',
                    'StringValue': 'comprehensive'
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger LLM processing: {e}")
        raise

# Health check endpoint
def health_check_handler(event, context):
    """Health check endpoint for entity screening service"""
    
    try:
        keywords_manager = EntityScreeningKeywords()
        keyword_stats = keywords_manager.get_keyword_statistics()
        
        health_status = {
            'service': 'entity-screening-service',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'keyword_statistics': keyword_stats
        }
        
        # Test keyword generation
        try:
            test_queries = keywords_manager.generate_entity_search_queries("Test Entity", max_queries=3)
            health_status['keyword_generation'] = 'operational'
            health_status['sample_queries_count'] = len(test_queries)
        except:
            health_status['keyword_generation'] = 'degraded'
            health_status['status'] = 'degraded'
        
        # Check API key access
        try:
            security_manager = SecurityManager()
            security_manager.get_secret('serper-api-key')
            health_status['api_key_access'] = 'operational'
        except:
            health_status['api_key_access'] = 'degraded'
            health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return create_secure_response(status_code, health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return create_secure_response(500, {
            'service': 'entity-screening-service',
            'status': 'unhealthy',
            'error': 'Health check system failure',
            'timestamp': datetime.now().isoformat()
        })

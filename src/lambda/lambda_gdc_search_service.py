#!/usr/bin/env python3
"""
GDC Search Service Lambda Function
Handles entity searches using AWS OpenSearch for Global Data Consortium index
"""

import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import shared modules
try:
    from shared.production_security_fixes import SecurityManager, InputValidator, create_secure_response
    from shared.production_monitoring import CloudWatchMetrics, PerformanceMonitor
    from shared.dynamodb_data_service import SearchResultsDataService
except ImportError:
    logger.error("Failed to import shared modules. Ensure they are in the deployment package.")
    raise

class OpenSearchClient:
    """AWS OpenSearch client for GDC entity searches"""
    
    def __init__(self):
        self.opensearch_client = boto3.client('opensearch-serverless')
        self.domain_endpoint = os.getenv('OPENSEARCH_DOMAIN_ENDPOINT')
        self.gdc_index = os.getenv('GDC_INDEX_NAME', 'gdc-entities')
    
    def search_entities(self, query: str, size: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Search GDC entities using OpenSearch
        
        Args:
            query: Search query string
            size: Number of results to return
            filters: Optional filters for entity type, jurisdiction, etc.
            
        Returns:
            List of entity search results
        """
        try:
            # Build OpenSearch query
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "entity_name^3",
                                        "entity_aliases^2", 
                                        "description",
                                        "risk_indicators",
                                        "regulatory_actions"
                                    ],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            }
                        ]
                    }
                },
                "size": size,
                "sort": [
                    {"_score": {"order": "desc"}},
                    {"last_updated": {"order": "desc"}}
                ],
                "_source": [
                    "entity_id",
                    "entity_name", 
                    "entity_type",
                    "jurisdiction",
                    "risk_indicators",
                    "regulatory_actions",
                    "last_updated",
                    "entity_aliases"
                ]
            }
            
            # Add filters if provided
            if filters:
                filter_clauses = []
                
                if filters.get('entity_type'):
                    filter_clauses.append({
                        "term": {"entity_type": filters['entity_type']}
                    })
                
                if filters.get('jurisdiction'):
                    filter_clauses.append({
                        "term": {"jurisdiction": filters['jurisdiction']}
                    })
                
                if filters.get('risk_level'):
                    filter_clauses.append({
                        "range": {"risk_score": {"gte": filters['risk_level']}}
                    })
                
                if filter_clauses:
                    search_body["query"]["bool"]["filter"] = filter_clauses
            
            # Execute search (Note: This is a simplified example)
            # In production, you would use the actual OpenSearch client
            logger.info(f"Executing OpenSearch query for: {query[:50]}...")
            
            # Mock response for demonstration - replace with actual OpenSearch call
            mock_results = self._generate_mock_results(query, size)
            
            return mock_results
            
        except Exception as e:
            logger.error(f"OpenSearch query failed: {e}")
            raise
    
    def _generate_mock_results(self, query: str, size: int) -> List[Dict]:
        """Generate mock results for demonstration purposes"""
        
        # Extract entity name from query for realistic mock data
        entity_keywords = query.lower().split()
        
        mock_entities = []
        
        if any(keyword in ['wells', 'fargo'] for keyword in entity_keywords):
            mock_entities.append({
                "entity_id": "WFC_US_BANK_001",
                "entity_name": "Wells Fargo & Company",
                "entity_type": "financial_institution",
                "jurisdiction": "US",
                "risk_indicators": ["regulatory_violations", "consumer_complaints", "settlement_history"],
                "regulatory_actions": [
                    "2020 - Consumer Financial Protection Bureau fine",
                    "2018 - Federal Reserve enforcement action"
                ],
                "last_updated": "2025-10-01T12:00:00Z",
                "entity_aliases": ["Wells Fargo Bank", "WFC"],
                "relevance_score": 0.95
            })
        
        if any(keyword in ['jpmorgan', 'chase', 'jp'] for keyword in entity_keywords):
            mock_entities.append({
                "entity_id": "JPM_US_BANK_001", 
                "entity_name": "JPMorgan Chase & Co.",
                "entity_type": "financial_institution",
                "jurisdiction": "US",
                "risk_indicators": ["money_laundering_concerns", "regulatory_violations"],
                "regulatory_actions": [
                    "2021 - FinCEN enforcement action",
                    "2019 - SEC settlement"
                ],
                "last_updated": "2025-09-28T15:30:00Z",
                "entity_aliases": ["Chase Bank", "JPM"],
                "relevance_score": 0.88
            })
        
        if any(keyword in ['goldman', 'sachs'] for keyword in entity_keywords):
            mock_entities.append({
                "entity_id": "GS_US_BANK_001",
                "entity_name": "Goldman Sachs Group Inc",
                "entity_type": "investment_bank",
                "jurisdiction": "US", 
                "risk_indicators": ["bribery_allegations", "regulatory_violations"],
                "regulatory_actions": [
                    "2020 - DOJ 1MDB settlement",
                    "2019 - SEC enforcement action"
                ],
                "last_updated": "2025-09-25T10:15:00Z",
                "entity_aliases": ["Goldman Sachs", "GS"],
                "relevance_score": 0.82
            })
        
        # If no specific matches, return generic financial entities
        if not mock_entities:
            mock_entities = [
                {
                    "entity_id": "GENERIC_ENTITY_001",
                    "entity_name": f"Entity matching '{query}'",
                    "entity_type": "corporation",
                    "jurisdiction": "US",
                    "risk_indicators": ["under_investigation"],
                    "regulatory_actions": [],
                    "last_updated": "2025-10-01T00:00:00Z",
                    "entity_aliases": [],
                    "relevance_score": 0.65
                }
            ]
        
        return mock_entities[:size]

def lambda_handler(event, context):
    """
    AWS Lambda handler for GDC OpenSearch entity screening
    
    Args:
        event: API Gateway event containing search parameters
        context: Lambda context object
        
    Returns:
        API Gateway response with search results
    """
    
    # Initialize components
    security_manager = SecurityManager()
    validator = InputValidator()
    metrics = CloudWatchMetrics()
    data_service = SearchResultsDataService()
    opensearch_client = OpenSearchClient()
    
    start_time = datetime.now()
    
    try:
        logger.info("GDC Search Service Lambda started")
        
        # Parse request body
        if 'body' in event and event['body']:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event
        
        # Extract and validate parameters
        try:
            query = validator.validate_search_query(body.get('query', ''))
            size = validator.validate_num_results(body.get('size', 10))
            index_name = body.get('index', 'gdc-entities')
            filters = body.get('filters', {})
            
            # Validate index name
            if not index_name.startswith('gdc-'):
                raise ValueError("Invalid index name. Must start with 'gdc-'")
                
        except ValueError as e:
            logger.warning(f"Input validation failed: {e}")
            return create_secure_response(400, {'error': str(e)})
        
        # Extract processing options
        enable_llm_processing = body.get('enable_llm_processing', True)
        store_results = body.get('store_results', True)
        callback_topic = body.get('callback_topic')
        
        # Perform OpenSearch query
        try:
            search_results = opensearch_client.search_entities(
                query=query,
                size=size,
                filters=filters
            )
            timestamp = datetime.now().isoformat()
            
            # Record search metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            metrics.record_search_metrics(query, len(search_results), processing_time, True)
            
            logger.info(f"OpenSearch completed: {len(search_results)} results for query length {len(query)}")
            
        except Exception as e:
            logger.error(f"OpenSearch query failed: {e}")
            metrics.record_search_metrics(query, 0, 0, False)
            return create_secure_response(500, {'error': 'Search service unavailable'})
        
        # Store results in DynamoDB if requested
        storage_result = None
        if store_results:
            try:
                # Convert OpenSearch results to standard format
                standardized_results = []
                for result in search_results:
                    standardized_results.append({
                        'title': result.get('entity_name', 'Unknown Entity'),
                        'url': f"gdc://entity/{result.get('entity_id', 'unknown')}",
                        'snippet': f"Entity Type: {result.get('entity_type', 'N/A')} | "
                                 f"Jurisdiction: {result.get('jurisdiction', 'N/A')} | "
                                 f"Risk Indicators: {', '.join(result.get('risk_indicators', []))}",
                        'position': standardized_results.__len__() + 1,
                        'entity_data': result  # Store full entity data
                    })
                
                storage_result = data_service.store_search_results(
                    query=query,
                    search_results=standardized_results,
                    metadata={
                        'source': 'gdc_opensearch',
                        'index_name': index_name,
                        'size_requested': size,
                        'filters_applied': filters,
                        'enable_llm_processing': enable_llm_processing,
                        'callback_topic': callback_topic,
                        'client_ip': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
                    }
                )
                logger.info(f"Stored GDC search results: {storage_result['query_hash']}")
                
            except Exception as e:
                logger.error(f"Failed to store search results: {e}")
                # Continue processing even if storage fails
        
        # Trigger LLM processing if requested
        llm_processing_triggered = False
        if enable_llm_processing and search_results:
            try:
                processing_timestamp = storage_result['timestamp'] if storage_result else timestamp
                topic_arn = callback_topic or os.getenv('LLM_PROCESSING_TOPIC')
                
                if topic_arn:
                    # Trigger LLM processing via SNS
                    sns_client = boto3.client('sns')
                    
                    message = {
                        'query': query,
                        'search_results': search_results[:3],  # Limit for LLM processing
                        'source': 'gdc_opensearch',
                        'timestamp': processing_timestamp,
                        'metadata': {
                            'index_name': index_name,
                            'total_results': len(search_results)
                        }
                    }
                    
                    sns_client.publish(
                        TopicArn=topic_arn,
                        Message=json.dumps(message),
                        Subject=f'GDC Entity Screening: {query[:50]}...'
                    )
                    
                    llm_processing_triggered = True
                    logger.info(f"Triggered LLM processing for GDC query: {query[:50]}...")
                    
                else:
                    logger.warning("No LLM processing topic available")
                    
            except Exception as e:
                logger.error(f"Failed to trigger LLM processing: {e}")
                # Don't fail the request if async processing fails
        
        # Build response
        response_data = {
            'query': query,
            'source': 'gdc_opensearch',
            'index': index_name,
            'results': search_results,
            'total_hits': len(search_results),
            'timestamp': timestamp,
            'llm_processing_triggered': llm_processing_triggered,
            'stored_in_database': storage_result is not None,
            'filters_applied': filters
        }
        
        if storage_result:
            response_data['storage_info'] = {
                'query_hash': storage_result['query_hash'],
                'storage_timestamp': storage_result['timestamp']
            }
        
        # Record final metrics
        total_processing_time = (datetime.now() - start_time).total_seconds()
        metrics.record_custom_metric('GDCSearchLatency', total_processing_time, 'Milliseconds')
        metrics.record_custom_metric('GDCSearchResults', len(search_results), 'Count')
        
        logger.info(f"GDC search completed successfully in {total_processing_time:.2f}s")
        
        return create_secure_response(200, response_data)
        
    except Exception as e:
        logger.error(f"Unexpected error in GDC search service: {e}")
        metrics.record_custom_metric('GDCSearchErrors', 1, 'Count')
        return create_secure_response(500, {
            'error': 'Internal server error',
            'timestamp': datetime.now().isoformat()
        })

def trigger_llm_processing(search_results: List[Dict], query: str, topic_arn: str, timestamp: str):
    """
    Trigger asynchronous LLM processing for GDC search results
    
    Args:
        search_results: List of entity search results
        query: Original search query
        topic_arn: SNS topic ARN for LLM processing
        timestamp: Processing timestamp
    """
    try:
        sns_client = boto3.client('sns')
        
        message = {
            'query': query,
            'search_results': search_results,
            'source': 'gdc_opensearch',
            'timestamp': timestamp,
            'processing_type': 'entity_risk_analysis'
        }
        
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject=f'GDC Entity Risk Analysis: {query[:50]}...'
        )
        
        logger.info(f"Successfully triggered LLM processing for {len(search_results)} GDC entities")
        
    except Exception as e:
        logger.error(f"Failed to trigger LLM processing: {e}")
        raise

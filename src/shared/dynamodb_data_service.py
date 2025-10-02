#!/usr/bin/env python3
"""
DynamoDB Data Service
Handles all DynamoDB operations for search agent results
"""

import os
import json
import boto3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import logging

logger = logging.getLogger(__name__)

class SearchResultsDataService:
    """
    Comprehensive DynamoDB service for search agent data
    """
    
    def __init__(self, table_name: str = None, region: str = 'us-east-1'):
        self.table_name = table_name or os.getenv('RESULTS_TABLE', 'search-analysis-results')
        self.region = region
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region)
            self.table = self.dynamodb.Table(self.table_name)
            self.client = boto3.client('dynamodb', region_name=region)
            logger.info(f"Initialized DynamoDB service for table: {self.table_name}")
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB service: {e}")
            raise
    
    def store_search_results(self, query: str, search_results: List[Dict], 
                           metadata: Dict = None) -> Dict[str, Any]:
        """
        Store raw search results from Serper API
        
        Args:
            query: Search query string
            search_results: List of search result dictionaries
            metadata: Additional metadata (request_id, timestamp, etc.)
            
        Returns:
            Dictionary with storage confirmation
        """
        try:
            timestamp = datetime.now().isoformat()
            query_hash = self._generate_query_hash(query)
            
            # TTL for 30 days
            ttl_timestamp = int((datetime.now() + timedelta(days=30)).timestamp())
            
            item = {
                'query': query,
                'timestamp': timestamp,
                'query_hash': query_hash,
                'record_type': 'SEARCH_RESULTS',
                'search_results': search_results,
                'total_results': len(search_results),
                'metadata': metadata or {},
                'processing_status': 'SEARCH_COMPLETED',
                'ttl': ttl_timestamp,
                'created_at': timestamp,
                'updated_at': timestamp
            }
            
            # Convert floats to Decimal for DynamoDB
            item = self._convert_floats_to_decimal(item)
            
            response = self.table.put_item(Item=item)
            
            logger.info(f"Stored search results for query: {query[:50]}...")
            
            return {
                'success': True,
                'query': query,
                'timestamp': timestamp,
                'query_hash': query_hash,
                'results_count': len(search_results),
                'dynamodb_response': response
            }
            
        except Exception as e:
            logger.error(f"Failed to store search results: {e}")
            raise
    
    def store_llm_analysis(self, query: str, timestamp: str, 
                          processed_results: List[Dict]) -> Dict[str, Any]:
        """
        Store LLM analysis results, updating existing search record
        
        Args:
            query: Original search query
            timestamp: Timestamp from search results
            processed_results: List of LLM processed results
            
        Returns:
            Dictionary with storage confirmation
        """
        try:
            current_time = datetime.now().isoformat()
            
            # Calculate processing metrics
            total_relevance = sum(r.get('relevance_score', 0) for r in processed_results)
            avg_relevance = total_relevance / len(processed_results) if processed_results else 0
            
            # Update the existing record
            update_expression = """
                SET 
                    llm_analysis = :analysis,
                    processing_status = :status,
                    processing_completed_at = :completed_at,
                    updated_at = :updated_at,
                    processing_metrics = :metrics,
                    record_type = :record_type
            """
            
            expression_values = {
                ':analysis': self._convert_floats_to_decimal(processed_results),
                ':status': 'ANALYSIS_COMPLETED',
                ':completed_at': current_time,
                ':updated_at': current_time,
                ':metrics': self._convert_floats_to_decimal({
                    'total_processed': len(processed_results),
                    'average_relevance': avg_relevance,
                    'processing_duration': self._calculate_processing_duration(timestamp, current_time),
                    'high_relevance_count': len([r for r in processed_results if r.get('relevance_score', 0) > 0.7])
                }),
                ':record_type': 'COMPLETE_ANALYSIS'
            }
            
            response = self.table.update_item(
                Key={
                    'query': query,
                    'timestamp': timestamp
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ReturnValues='ALL_NEW'
            )
            
            logger.info(f"Stored LLM analysis for query: {query[:50]}...")
            
            return {
                'success': True,
                'query': query,
                'timestamp': timestamp,
                'processed_count': len(processed_results),
                'average_relevance': avg_relevance,
                'updated_item': response.get('Attributes')
            }
            
        except Exception as e:
            logger.error(f"Failed to store LLM analysis: {e}")
            raise
    
    def get_search_results(self, query: str, timestamp: str = None) -> Optional[Dict]:
        """
        Retrieve search results by query and timestamp
        
        Args:
            query: Search query string
            timestamp: Specific timestamp (optional, gets latest if not provided)
            
        Returns:
            Dictionary with search results or None if not found
        """
        try:
            if timestamp:
                # Get specific result
                response = self.table.get_item(
                    Key={
                        'query': query,
                        'timestamp': timestamp
                    }
                )
                item = response.get('Item')
            else:
                # Get latest result for query
                response = self.table.query(
                    KeyConditionExpression='query = :query',
                    ExpressionAttributeValues={':query': query},
                    ScanIndexForward=False,  # Latest first
                    Limit=1
                )
                items = response.get('Items', [])
                item = items[0] if items else None
            
            if item:
                # Convert Decimal back to float
                item = self._convert_decimal_to_float(item)
                logger.info(f"Retrieved results for query: {query[:50]}...")
                return item
            else:
                logger.warning(f"No results found for query: {query[:50]}...")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve search results: {e}")
            raise
    
    def get_recent_searches(self, limit: int = 10, days_back: int = 7) -> List[Dict]:
        """
        Get recent search queries and their status
        
        Args:
            limit: Maximum number of results to return
            days_back: Number of days to look back
            
        Returns:
            List of recent search summaries
        """
        try:
            # Calculate date threshold
            threshold_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            # Scan for recent items (in production, consider using GSI)
            response = self.table.scan(
                FilterExpression='created_at > :threshold',
                ExpressionAttributeValues={':threshold': threshold_date},
                ProjectionExpression='query, timestamp, processing_status, total_results, processing_metrics',
                Limit=limit * 2  # Get more to account for filtering
            )
            
            items = response.get('Items', [])
            
            # Sort by timestamp and limit
            items = sorted(items, key=lambda x: x.get('timestamp', ''), reverse=True)[:limit]
            
            # Convert Decimal to float
            items = [self._convert_decimal_to_float(item) for item in items]
            
            logger.info(f"Retrieved {len(items)} recent searches")
            return items
            
        except Exception as e:
            logger.error(f"Failed to retrieve recent searches: {e}")
            raise
    
    def search_by_keywords(self, keywords: List[str], limit: int = 20) -> List[Dict]:
        """
        Search for results containing specific keywords
        
        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results
            
        Returns:
            List of matching search results
        """
        try:
            results = []
            
            # Simple approach: scan and filter (consider GSI for production)
            for keyword in keywords:
                response = self.table.scan(
                    FilterExpression='contains(query, :keyword)',
                    ExpressionAttributeValues={':keyword': keyword.lower()},
                    Limit=limit
                )
                
                items = response.get('Items', [])
                results.extend(items)
            
            # Remove duplicates and sort
            seen = set()
            unique_results = []
            
            for item in results:
                key = (item.get('query', ''), item.get('timestamp', ''))
                if key not in seen:
                    seen.add(key)
                    unique_results.append(self._convert_decimal_to_float(item))
            
            # Sort by timestamp, most recent first
            unique_results = sorted(unique_results, 
                                  key=lambda x: x.get('timestamp', ''), 
                                  reverse=True)[:limit]
            
            logger.info(f"Found {len(unique_results)} results for keywords: {keywords}")
            return unique_results
            
        except Exception as e:
            logger.error(f"Failed to search by keywords: {e}")
            raise
    
    def get_processing_statistics(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Get processing statistics for the specified time period
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            threshold_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            response = self.table.scan(
                FilterExpression='created_at > :threshold',
                ExpressionAttributeValues={':threshold': threshold_date},
                ProjectionExpression='''
                    processing_status, total_results, processing_metrics, 
                    created_at, processing_completed_at
                '''
            )
            
            items = response.get('Items', [])
            items = [self._convert_decimal_to_float(item) for item in items]
            
            # Calculate statistics
            total_searches = len(items)
            completed_analyses = len([i for i in items if i.get('processing_status') == 'ANALYSIS_COMPLETED'])
            
            total_results_processed = sum(i.get('total_results', 0) for i in items)
            
            avg_relevance_scores = []
            processing_times = []
            
            for item in items:
                metrics = item.get('processing_metrics', {})
                if 'average_relevance' in metrics:
                    avg_relevance_scores.append(metrics['average_relevance'])
                if 'processing_duration' in metrics:
                    processing_times.append(metrics['processing_duration'])
            
            stats = {
                'period_days': days_back,
                'total_searches': total_searches,
                'completed_analyses': completed_analyses,
                'completion_rate': completed_analyses / total_searches if total_searches > 0 else 0,
                'total_results_processed': total_results_processed,
                'average_results_per_search': total_results_processed / total_searches if total_searches > 0 else 0,
                'average_relevance_score': sum(avg_relevance_scores) / len(avg_relevance_scores) if avg_relevance_scores else 0,
                'average_processing_time_seconds': sum(processing_times) / len(processing_times) if processing_times else 0,
                'high_relevance_searches': len([s for s in avg_relevance_scores if s > 0.7])
            }
            
            logger.info(f"Generated statistics for {days_back} days")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get processing statistics: {e}")
            raise
    
    def cleanup_expired_records(self) -> Dict[str, int]:
        """
        Clean up expired records (beyond TTL)
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            current_timestamp = int(datetime.now().timestamp())
            
            # Scan for expired items
            response = self.table.scan(
                FilterExpression='attribute_exists(ttl) AND ttl < :current_time',
                ExpressionAttributeValues={':current_time': current_timestamp},
                ProjectionExpression='query, timestamp'
            )
            
            expired_items = response.get('Items', [])
            deleted_count = 0
            
            # Delete expired items
            with self.table.batch_writer() as batch:
                for item in expired_items:
                    batch.delete_item(
                        Key={
                            'query': item['query'],
                            'timestamp': item['timestamp']
                        }
                    )
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} expired records")
            
            return {
                'deleted_count': deleted_count,
                'cleanup_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired records: {e}")
            raise
    
    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for the query for indexing"""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def _calculate_processing_duration(self, start_time: str, end_time: str) -> float:
        """Calculate processing duration in seconds"""
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            return (end - start).total_seconds()
        except:
            return 0.0
    
    def _convert_floats_to_decimal(self, obj):
        """Convert floats to Decimal for DynamoDB compatibility"""
        if isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(v) for v in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        else:
            return obj
    
    def _convert_decimal_to_float(self, obj):
        """Convert Decimal back to float for JSON serialization"""
        if isinstance(obj, dict):
            return {k: self._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal_to_float(v) for v in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj

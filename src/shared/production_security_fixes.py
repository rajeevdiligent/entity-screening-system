#!/usr/bin/env python3
"""
Production Security Fixes for Search Agent Solution
"""

import os
import json
import boto3
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SecurityManager:
    """Handles security-related operations for production deployment"""
    
    def __init__(self):
        self.secrets_client = boto3.client('secretsmanager')
        self.ssm_client = boto3.client('ssm')
    
    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret from AWS Secrets Manager"""
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise
    
    def get_parameter(self, parameter_name: str, decrypt: bool = True) -> str:
        """Retrieve parameter from AWS Systems Manager Parameter Store"""
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=decrypt
            )
            return response['Parameter']['Value']
        except Exception as e:
            logger.error(f"Failed to retrieve parameter {parameter_name}: {e}")
            raise
    
    def validate_request(self, event: Dict[str, Any], context: Any) -> bool:
        """Validate incoming Lambda request for security"""
        try:
            # Basic request validation
            if not event:
                logger.warning("Empty event received")
                return False
            
            # Check for SNS message structure (for LLM service)
            if 'Records' in event:
                for record in event['Records']:
                    if record.get('EventSource') == 'aws:sns':
                        # Valid SNS message
                        return True
            
            # Check for API Gateway structure (for search service)
            if 'httpMethod' in event or 'body' in event:
                return True
            
            # Allow direct invocation for testing
            if 'query' in event:
                return True
            
            logger.info("Request validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {e}")
            return False

class InputValidator:
    """Validates and sanitizes input data"""
    
    @staticmethod
    def validate_search_query(query: str) -> str:
        """Validate and sanitize search query"""
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        
        # Remove potentially harmful characters
        sanitized = re.sub(r'[<>"\']', '', query.strip())
        
        # Limit length
        if len(sanitized) > 500:
            raise ValueError("Query too long (max 500 characters)")
        
        if len(sanitized) < 3:
            raise ValueError("Query too short (min 3 characters)")
        
        return sanitized
    
    @staticmethod
    def validate_num_results(num_results: Any) -> int:
        """Validate number of results parameter"""
        try:
            num = int(num_results)
            if num < 1 or num > 100:
                raise ValueError("Number of results must be between 1 and 100")
            return num
        except (ValueError, TypeError):
            raise ValueError("Invalid number of results")
    
    @staticmethod
    def validate_api_key_format(api_key: str) -> bool:
        """Validate API key format (basic check)"""
        if not api_key or len(api_key) < 20:
            return False
        # Add more specific validation based on your API key formats
        return True
    
    @staticmethod
    def validate_llm_event(event: Dict[str, Any]) -> bool:
        """Validate LLM processing event structure"""
        try:
            # Check for SNS message structure
            if 'Records' in event:
                for record in event['Records']:
                    if record.get('EventSource') == 'aws:sns':
                        message = record.get('Sns', {}).get('Message')
                        if message:
                            # Try to parse the message
                            import json
                            message_data = json.loads(message)
                            if 'query' in message_data and 'search_results' in message_data:
                                return True
            
            # Check for direct invocation
            if 'query' in event and 'search_results' in event:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"LLM event validation failed: {e}")
            return False
    
    @staticmethod
    def validate_gdc_search_input(query: str, index: str, size: int) -> bool:
        """Validate GDC search input parameters"""
        try:
            if not query or not isinstance(query, str) or len(query.strip()) == 0:
                return False
            
            if not index or not isinstance(index, str):
                return False
            
            if not isinstance(size, int) or size < 1 or size > 100:
                return False
            
            return True
            
        except Exception:
            return False

class RateLimiter:
    """Simple rate limiting implementation"""
    
    def __init__(self, dynamodb_table: str):
        self.table_name = dynamodb_table
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(dynamodb_table)
    
    def check_rate_limit(self, client_id: str, limit: int = 100, 
                        window_minutes: int = 60) -> bool:
        """Check if client has exceeded rate limit"""
        try:
            from datetime import datetime, timedelta
            
            current_time = datetime.now()
            window_start = current_time - timedelta(minutes=window_minutes)
            
            # Query recent requests for this client
            response = self.table.query(
                KeyConditionExpression='client_id = :client_id AND request_time > :window_start',
                ExpressionAttributeValues={
                    ':client_id': client_id,
                    ':window_start': window_start.isoformat()
                }
            )
            
            request_count = len(response.get('Items', []))
            
            if request_count >= limit:
                logger.warning(f"Rate limit exceeded for client {client_id}")
                return False
            
            # Record this request
            self.table.put_item(
                Item={
                    'client_id': client_id,
                    'request_time': current_time.isoformat(),
                    'ttl': int((current_time + timedelta(hours=24)).timestamp())
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open in case of errors
            return True

def create_secure_response(status_code: int, body: Dict[str, Any], 
                          headers: Dict[str, str] = None) -> Dict:
    """Create secure API response with proper headers"""
    
    security_headers = {
        'Content-Type': 'application/json',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    if headers:
        security_headers.update(headers)
    
    # Remove sensitive information from error responses
    if status_code >= 400 and 'error' in body:
        # Don't expose internal error details
        if status_code == 500:
            body = {'error': 'Internal server error'}
    
    return {
        'statusCode': status_code,
        'headers': security_headers,
        'body': json.dumps(body, default=str)
    }

# Example usage in Lambda functions:
def secure_lambda_handler(event, context):
    """Example of secure Lambda handler implementation"""
    
    try:
        # Initialize security components
        security_manager = SecurityManager()
        validator = InputValidator()
        
        # Get API key securely
        api_key = security_manager.get_secret('serper-api-key')
        
        # Validate input
        query = validator.validate_search_query(event.get('query', ''))
        num_results = validator.validate_num_results(event.get('num_results', 10))
        
        # Rate limiting (if implemented)
        client_id = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        # rate_limiter = RateLimiter('rate-limit-table')
        # if not rate_limiter.check_rate_limit(client_id):
        #     return create_secure_response(429, {'error': 'Rate limit exceeded'})
        
        # Process request...
        result = {'message': 'Success', 'query': query, 'num_results': num_results}
        
        return create_secure_response(200, result)
        
    except ValueError as e:
        return create_secure_response(400, {'error': str(e)})
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return create_secure_response(500, {'error': 'Internal server error'})

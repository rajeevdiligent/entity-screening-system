#!/usr/bin/env python3
"""
Simple Search Lambda - Inline Version
"""

import json
import os
import boto3
import requests
from datetime import datetime
from decimal import Decimal

def lambda_handler(event, context):
    """Lambda handler for search service"""
    try:
        # Parse event body if it's from API Gateway
        if 'body' in event and event['body']:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event
        
        query = body.get('query', '')
        num_results = body.get('num_results', 5)
        enable_llm = body.get('enable_llm_processing', True)
        
        if not query:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Query parameter is required'})
            }
        
        print(f"Processing search query: {query}")
        
        # Get search results from Serper API
        search_results = search_with_serper(query, num_results)
        
        # Store results in DynamoDB
        timestamp = datetime.now().isoformat()
        store_search_results(query, search_results, timestamp)
        
        # Trigger LLM processing if enabled
        llm_triggered = False
        if enable_llm and search_results:
            llm_triggered = trigger_llm_processing(query, search_results, timestamp)
        
        response_body = {
            'query': query,
            'search_results': search_results,
            'results_count': len(search_results),
            'timestamp': timestamp,
            'llm_processing_triggered': llm_triggered
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error in search service: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def search_with_serper(query: str, num_results: int = 5):
    """Search using Serper API"""
    try:
        api_key = os.getenv('SERPER_API_KEY', '23169f82aceef5712e77c44b0203ba7622417e72')
        
        url = "https://google.serper.dev/search"
        payload = {"q": query, "num": num_results}
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        organic_results = data.get('organic', [])
        
        search_results = []
        for result in organic_results:
            search_results.append({
                'title': result.get('title', ''),
                'url': result.get('link', ''),
                'snippet': result.get('snippet', ''),
                'position': result.get('position', 0)
            })
        
        print(f"Retrieved {len(search_results)} search results")
        return search_results
        
    except Exception as e:
        print(f"Error searching with Serper: {e}")
        return []

def store_search_results(query: str, search_results: list, timestamp: str):
    """Store search results in DynamoDB"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table_name = os.getenv('RESULTS_TABLE', 'search-analysis-results')
        table = dynamodb.Table(table_name)
        
        def convert_floats_to_decimal(obj):
            if isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(v) for v in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            else:
                return obj
        
        converted_results = convert_floats_to_decimal(search_results)
        
        item = {
            'query': query,
            'timestamp': timestamp,
            'record_type': 'SEARCH_RESULTS',
            'search_results': converted_results,
            'total_results': len(search_results),
            'processing_status': 'SEARCH_COMPLETED',
            'created_at': timestamp
        }
        
        table.put_item(Item=item)
        print(f"Stored search results in DynamoDB for query: {query[:50]}...")
        
    except Exception as e:
        print(f"Failed to store search results: {e}")

def trigger_llm_processing(query: str, search_results: list, timestamp: str):
    """Trigger LLM processing via SNS"""
    try:
        sns_client = boto3.client('sns', region_name='us-east-1')
        topic_arn = os.getenv('LLM_PROCESSING_TOPIC')
        
        if not topic_arn:
            print("No LLM processing topic configured")
            return False
        
        message = {
            'query': query,
            'search_results': search_results,
            'timestamp': timestamp
        }
        
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject=f'LLM Processing Request: {query[:50]}'
        )
        
        print(f"Triggered LLM processing for query: {query[:50]}...")
        return True
        
    except Exception as e:
        print(f"Failed to trigger LLM processing: {e}")
        return False

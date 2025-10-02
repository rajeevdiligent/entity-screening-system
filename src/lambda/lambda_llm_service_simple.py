#!/usr/bin/env python3
"""
LLM Risk Scoring Service Lambda - Simplified Version
Processes search results with Amazon Nova LLM for comprehensive risk assessment
"""

import json
import os
import boto3
from typing import List, Dict, Any
from datetime import datetime

def lambda_handler(event, context):
    """
    Lambda handler for LLM risk analysis
    """
    
    try:
        print(f"LLM service received event: {json.dumps(event, default=str)}")
        
        # Handle different event sources
        if 'Records' in event:
            # SNS/SQS triggered
            for record in event['Records']:
                if 'Sns' in record:
                    # SNS message
                    message = json.loads(record['Sns']['Message'])
                    process_search_results(message)
                elif 'body' in record:
                    # SQS message
                    message = json.loads(record['body'])
                    process_search_results(message)
        else:
            # Direct invocation
            process_search_results(event)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'LLM processing completed successfully'})
        }
        
    except Exception as e:
        print(f"Error in LLM service: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def process_search_results(message: Dict):
    """Process search results with Nova LLM and store risk analysis in DynamoDB"""
    
    search_results = message.get('search_results', [])
    query = message.get('query', '')
    timestamp = message.get('timestamp', datetime.now().isoformat())
    
    if not search_results:
        print("No search results to process")
        return
    
    print(f"Processing {len(search_results)} results for query: {query[:50]}...")
    
    processed_results = []
    
    # Process each result with Nova LLM
    for idx, result in enumerate(search_results):
        try:
            print(f"Processing result {idx + 1}/{len(search_results)}: {result.get('title', 'Unknown')[:50]}...")
            processed = analyze_with_nova_llm(result, query)
            processed_results.append(processed)
            
        except Exception as e:
            print(f"Failed to process result {idx + 1}: {e}")
            # Add error result with basic risk assessment
            processed_results.append({
                'original_result': result,
                'summary': result.get('snippet', '')[:200],
                'risk_assessment': {
                    'overall_risk_score': 0.5,
                    'risk_level': 'MEDIUM',
                    'financial_crimes_risk': 0.5,
                    'corruption_risk': 0.5,
                    'regulatory_risk': 0.5,
                    'reputational_risk': 0.5,
                    'composite_risk_score': 0.5
                },
                'key_findings': [f"Error processing: {str(e)}"],
                'risk_factors': ["Unable to analyze with LLM"],
                'compliance_concerns': ["Manual review recommended"],
                'source_credibility': {
                    'credibility_score': 0.5,
                    'source_type': 'unknown',
                    'publication_date': 'unknown'
                },
                'relevance_score': 0.5,
                'confidence_level': 0.3,
                'processing_error': True,
                'processing_timestamp': datetime.now().isoformat()
            })
    
    # Store LLM analysis results in DynamoDB
    try:
        store_llm_analysis(query, timestamp, processed_results)
        print(f"Successfully stored LLM analysis for {len(processed_results)} results")
        
    except Exception as e:
        print(f"Failed to store LLM analysis: {e}")

def analyze_with_nova_llm(result: Dict, context: str) -> Dict:
    """Analyze single result with Nova LLM for comprehensive risk scoring"""
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    # Sanitize inputs
    title = str(result.get('title', ''))[:200]
    url = str(result.get('url', ''))[:500]
    snippet = str(result.get('snippet', ''))[:1000]
    context = str(context)[:200]
    
    prompt = f"""
    Analyze this search result for comprehensive entity screening and risk assessment:
    
    Title: {title}
    URL: {url}
    Content: {snippet}
    Search Context: {context}
    
    Provide a detailed risk analysis in JSON format:
    {{
        "summary": "concise summary of the content (max 150 words)",
        "risk_assessment": {{
            "overall_risk_score": 0.75,
            "risk_level": "HIGH",
            "financial_crimes_risk": 0.8,
            "corruption_risk": 0.6,
            "regulatory_risk": 0.7,
            "reputational_risk": 0.9
        }},
        "key_findings": [
            "Specific finding 1 with evidence",
            "Specific finding 2 with evidence",
            "Specific finding 3 with evidence"
        ],
        "risk_factors": [
            "Factor 1: Description and impact",
            "Factor 2: Description and impact"
        ],
        "compliance_concerns": [
            "Concern 1: Regulatory implication",
            "Concern 2: Legal implication"
        ],
        "source_credibility": {{
            "credibility_score": 0.9,
            "source_type": "government/news/academic/legal",
            "publication_date": "estimated date if available"
        }},
        "relevance_score": 0.85,
        "confidence_level": 0.8
    }}
    
    Risk scoring guidelines:
    - 0.0-0.3: LOW risk
    - 0.4-0.6: MEDIUM risk  
    - 0.7-0.8: HIGH risk
    - 0.9-1.0: CRITICAL risk
    
    Focus on financial crimes, corruption, regulatory violations, and reputational issues.
    """
    
    model_id = "amazon.nova-micro-v1:0"
    
    body = json.dumps({
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 500,
            "temperature": 0.3,
            "topP": 0.9
        }
    })
    
    response = bedrock.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json"
    )
    
    response_body = json.loads(response.get('body').read())
    llm_response = response_body.get('results')[0].get('outputText')
    
    # Parse JSON response
    try:
        start = llm_response.find('{')
        end = llm_response.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = llm_response[start:end]
            parsed = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
    except Exception as e:
        print(f"JSON parsing error: {e}")
        parsed = {
            "summary": llm_response[:200] if llm_response else "No summary available",
            "risk_assessment": {
                "overall_risk_score": 0.5,
                "risk_level": "MEDIUM",
                "financial_crimes_risk": 0.5,
                "corruption_risk": 0.5,
                "regulatory_risk": 0.5,
                "reputational_risk": 0.5
            },
            "key_findings": ["Parsing error - manual review required"],
            "risk_factors": ["Unable to parse LLM response"],
            "compliance_concerns": ["Manual review recommended"],
            "source_credibility": {
                "credibility_score": 0.5,
                "source_type": "unknown",
                "publication_date": "unknown"
            },
            "relevance_score": 0.5,
            "confidence_level": 0.3
        }
    
    # Calculate composite risk score
    risk_assessment = parsed.get('risk_assessment', {})
    composite_risk = calculate_composite_risk_score(risk_assessment)
    
    return {
        'original_result': result,
        'summary': parsed.get('summary', ''),
        'risk_assessment': {
            'overall_risk_score': risk_assessment.get('overall_risk_score', 0.5),
            'risk_level': risk_assessment.get('risk_level', 'MEDIUM'),
            'financial_crimes_risk': risk_assessment.get('financial_crimes_risk', 0.5),
            'corruption_risk': risk_assessment.get('corruption_risk', 0.5),
            'regulatory_risk': risk_assessment.get('regulatory_risk', 0.5),
            'reputational_risk': risk_assessment.get('reputational_risk', 0.5),
            'composite_risk_score': composite_risk
        },
        'key_findings': parsed.get('key_findings', []),
        'risk_factors': parsed.get('risk_factors', []),
        'compliance_concerns': parsed.get('compliance_concerns', []),
        'source_credibility': parsed.get('source_credibility', {}),
        'relevance_score': parsed.get('relevance_score', 0.5),
        'confidence_level': parsed.get('confidence_level', 0.5),
        'processing_timestamp': datetime.now().isoformat()
    }

def calculate_composite_risk_score(risk_assessment: Dict) -> float:
    """Calculate a weighted composite risk score"""
    try:
        # Risk component weights (totaling 1.0)
        weights = {
            'financial_crimes_risk': 0.35,  # Highest weight for financial crimes
            'corruption_risk': 0.25,        # High weight for corruption
            'regulatory_risk': 0.25,        # High weight for regulatory issues
            'reputational_risk': 0.15       # Lower weight for reputational risk
        }
        
        composite_score = 0.0
        for risk_type, weight in weights.items():
            risk_value = risk_assessment.get(risk_type, 0.5)
            composite_score += risk_value * weight
        
        # Ensure score is within bounds
        composite_score = max(0.0, min(1.0, composite_score))
        
        return round(composite_score, 3)
        
    except Exception as e:
        print(f"Error calculating composite risk score: {e}")
        return 0.5  # Default medium risk

def store_llm_analysis(query: str, timestamp: str, processed_results: List[Dict]):
    """Store LLM analysis results in DynamoDB"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.getenv('RESULTS_TABLE', 'search-analysis-results'))
        
        # Generate a unique hash for this analysis
        import hashlib
        analysis_hash = hashlib.md5(f"{query}_{timestamp}_llm_analysis".encode()).hexdigest()
        
        table.put_item(
            Item={
                'query_hash': analysis_hash,
                'query': query,
                'timestamp': timestamp,
                'record_type': 'LLM_ANALYSIS',
                'llm_analysis': processed_results,
                'total_count': len(processed_results),
                'processing_status': 'ANALYSIS_COMPLETED',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'ttl': int(datetime.now().timestamp()) + (30 * 24 * 60 * 60)  # 30 days TTL
            }
        )
        print(f"Stored LLM analysis with hash: {analysis_hash}")
        
    except Exception as e:
        print(f"Failed to store LLM analysis: {e}")
        raise

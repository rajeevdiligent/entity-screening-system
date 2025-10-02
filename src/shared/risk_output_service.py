#!/usr/bin/env python3
"""
Risk Output Service
Handles storage of risk scores in output table and SQS notifications
"""

import json
import os
import boto3
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class RiskOutputService:
    """Service for storing risk scores and sending notifications"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.sqs = boto3.client('sqs')
        
        # Table and queue configuration
        self.output_table_name = os.getenv('RISK_OUTPUT_TABLE_NAME', 'entity-risk-scores')
        self.notification_queue_url = os.getenv('RISK_NOTIFICATION_QUEUE_URL')
        
        # Initialize output table
        self.output_table = self.dynamodb.Table(self.output_table_name)
    
    def store_risk_assessment(self, 
                            query: str, 
                            entity_data: Dict, 
                            risk_analysis: Dict, 
                            source: str = 'unknown') -> Dict:
        """
        Store risk assessment results in the output table
        
        Args:
            query: Original search query
            entity_data: Entity information from search
            risk_analysis: LLM risk analysis results
            source: Source of the data (serper_api, gdc_opensearch, etc.)
            
        Returns:
            Storage result with record ID and timestamp
        """
        try:
            timestamp = datetime.now().isoformat()
            record_id = f"{hash(query + timestamp)}_{source}"
            
            # Extract entity information
            entity_name = self._extract_entity_name(entity_data, query)
            entity_type = entity_data.get('entity_type', 'unknown')
            jurisdiction = entity_data.get('jurisdiction', 'unknown')
            
            # Prepare risk score record
            risk_record = {
                'record_id': record_id,
                'query': query,
                'entity_name': entity_name,
                'entity_type': entity_type,
                'jurisdiction': jurisdiction,
                'source': source,
                'timestamp': timestamp,
                'risk_assessment': self._convert_floats_to_decimal(risk_analysis.get('risk_assessment', {})),
                'overall_risk_score': self._convert_floats_to_decimal(
                    risk_analysis.get('risk_assessment', {}).get('overall_risk_score', 0.0)
                ),
                'risk_level': risk_analysis.get('risk_assessment', {}).get('risk_level', 'UNKNOWN'),
                'key_findings': risk_analysis.get('key_findings', []),
                'risk_factors': risk_analysis.get('risk_factors', []),
                'compliance_concerns': risk_analysis.get('compliance_concerns', []),
                'confidence_level': self._convert_floats_to_decimal(
                    risk_analysis.get('confidence_level', 0.0)
                ),
                'processing_status': 'COMPLETED',
                'created_at': timestamp,
                'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
            
            # Add entity-specific data if available
            if 'entity_id' in entity_data:
                risk_record['entity_id'] = entity_data['entity_id']
            
            if 'risk_indicators' in entity_data:
                risk_record['source_risk_indicators'] = entity_data['risk_indicators']
            
            # Store in output table
            self.output_table.put_item(Item=risk_record)
            
            logger.info(f"Stored risk assessment for {entity_name} with record ID: {record_id}")
            
            return {
                'record_id': record_id,
                'timestamp': timestamp,
                'entity_name': entity_name,
                'risk_level': risk_record['risk_level'],
                'overall_risk_score': float(risk_record['overall_risk_score'])
            }
            
        except Exception as e:
            logger.error(f"Failed to store risk assessment: {e}")
            raise
    
    def send_risk_notification(self, risk_record: Dict) -> bool:
        """
        Send notification to SQS queue about new risk assessment
        
        Args:
            risk_record: Risk assessment record data
            
        Returns:
            True if notification sent successfully
        """
        try:
            if not self.notification_queue_url:
                logger.warning("No notification queue URL configured")
                return False
            
            # Prepare notification message
            notification = {
                'event_type': 'RISK_ASSESSMENT_COMPLETED',
                'record_id': risk_record['record_id'],
                'entity_name': risk_record['entity_name'],
                'risk_level': risk_record['risk_level'],
                'overall_risk_score': float(risk_record['overall_risk_score']),
                'timestamp': risk_record['timestamp'],
                'source': risk_record.get('source', 'unknown'),
                'requires_review': self._requires_manual_review(risk_record),
                'notification_timestamp': datetime.now().isoformat()
            }
            
            # Add priority based on risk level
            priority = self._get_notification_priority(risk_record['risk_level'])
            
            # Send to SQS
            response = self.sqs.send_message(
                QueueUrl=self.notification_queue_url,
                MessageBody=json.dumps(notification),
                MessageAttributes={
                    'Priority': {
                        'StringValue': priority,
                        'DataType': 'String'
                    },
                    'RiskLevel': {
                        'StringValue': risk_record['risk_level'],
                        'DataType': 'String'
                    },
                    'EntityName': {
                        'StringValue': risk_record['entity_name'][:100],  # Limit length
                        'DataType': 'String'
                    }
                }
            )
            
            logger.info(f"Sent risk notification for {risk_record['entity_name']} "
                       f"(Risk: {risk_record['risk_level']}) - Message ID: {response['MessageId']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send risk notification: {e}")
            return False
    
    def get_risk_assessments(self, 
                           entity_name: Optional[str] = None,
                           risk_level: Optional[str] = None,
                           limit: int = 50) -> List[Dict]:
        """
        Retrieve risk assessments from output table
        
        Args:
            entity_name: Filter by entity name
            risk_level: Filter by risk level
            limit: Maximum number of records to return
            
        Returns:
            List of risk assessment records
        """
        try:
            # Build scan parameters
            scan_params = {
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }
            
            # Add filters if specified
            filter_expressions = []
            expression_values = {}
            
            if entity_name:
                filter_expressions.append('contains(entity_name, :entity_name)')
                expression_values[':entity_name'] = entity_name
            
            if risk_level:
                filter_expressions.append('risk_level = :risk_level')
                expression_values[':risk_level'] = risk_level
            
            if filter_expressions:
                scan_params['FilterExpression'] = ' AND '.join(filter_expressions)
                scan_params['ExpressionAttributeValues'] = expression_values
            
            # Perform scan
            response = self.output_table.scan(**scan_params)
            
            # Convert Decimal back to float for JSON serialization
            results = []
            for item in response.get('Items', []):
                converted_item = self._convert_decimal_to_float(item)
                results.append(converted_item)
            
            logger.info(f"Retrieved {len(results)} risk assessment records")
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve risk assessments: {e}")
            return []
    
    def _extract_entity_name(self, entity_data: Dict, query: str) -> str:
        """Extract entity name from entity data or query"""
        if 'entity_name' in entity_data:
            return entity_data['entity_name']
        elif 'title' in entity_data:
            return entity_data['title']
        else:
            # Extract from query - take first few words
            words = query.split()[:3]
            return ' '.join(words).title()
    
    def _requires_manual_review(self, risk_record: Dict) -> bool:
        """Determine if risk assessment requires manual review"""
        risk_level = risk_record.get('risk_level', 'UNKNOWN')
        overall_score = float(risk_record.get('overall_risk_score', 0))
        confidence = float(risk_record.get('confidence_level', 0))
        
        # High risk or low confidence requires review
        return (
            risk_level in ['HIGH', 'CRITICAL'] or
            overall_score >= 0.8 or
            confidence < 0.6 or
            risk_level == 'UNKNOWN'
        )
    
    def _get_notification_priority(self, risk_level: str) -> str:
        """Get notification priority based on risk level"""
        priority_map = {
            'CRITICAL': 'HIGH',
            'HIGH': 'HIGH',
            'MEDIUM': 'NORMAL',
            'LOW': 'LOW',
            'UNKNOWN': 'NORMAL'
        }
        return priority_map.get(risk_level, 'NORMAL')
    
    def _convert_floats_to_decimal(self, obj):
        """Convert float values to Decimal for DynamoDB storage"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    def _convert_decimal_to_float(self, obj):
        """Convert Decimal values back to float for JSON serialization"""
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimal_to_float(item) for item in obj]
        else:
            return obj

class RiskNotificationProcessor:
    """Processor for handling risk notification messages from SQS"""
    
    def __init__(self):
        self.sqs = boto3.client('sqs')
        self.sns = boto3.client('sns')
        
    def process_notification(self, message: Dict) -> bool:
        """
        Process a risk notification message
        
        Args:
            message: SQS message containing risk notification
            
        Returns:
            True if processed successfully
        """
        try:
            # Parse message body
            if isinstance(message.get('Body'), str):
                notification_data = json.loads(message['Body'])
            else:
                notification_data = message.get('Body', {})
            
            logger.info(f"Processing risk notification for entity: "
                       f"{notification_data.get('entity_name', 'Unknown')}")
            
            # Determine actions based on risk level and priority
            risk_level = notification_data.get('risk_level', 'UNKNOWN')
            requires_review = notification_data.get('requires_review', False)
            
            actions_taken = []
            
            # High-risk entities require immediate attention
            if risk_level in ['HIGH', 'CRITICAL']:
                actions_taken.append('HIGH_RISK_ALERT')
                self._send_high_risk_alert(notification_data)
            
            # Low confidence requires manual review
            if requires_review:
                actions_taken.append('MANUAL_REVIEW_REQUIRED')
                self._queue_for_manual_review(notification_data)
            
            # Log processing completion
            logger.info(f"Risk notification processed successfully. Actions: {actions_taken}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process risk notification: {e}")
            return False
    
    def _send_high_risk_alert(self, notification_data: Dict):
        """Send high-risk alert to appropriate channels"""
        try:
            alert_topic = os.getenv('HIGH_RISK_ALERT_TOPIC')
            if alert_topic:
                alert_message = {
                    'alert_type': 'HIGH_RISK_ENTITY',
                    'entity_name': notification_data.get('entity_name'),
                    'risk_level': notification_data.get('risk_level'),
                    'overall_risk_score': notification_data.get('overall_risk_score'),
                    'record_id': notification_data.get('record_id'),
                    'timestamp': notification_data.get('timestamp'),
                    'action_required': 'IMMEDIATE_REVIEW'
                }
                
                self.sns.publish(
                    TopicArn=alert_topic,
                    Message=json.dumps(alert_message),
                    Subject=f"HIGH RISK ALERT: {notification_data.get('entity_name', 'Unknown Entity')}"
                )
                
                logger.info(f"High-risk alert sent for {notification_data.get('entity_name')}")
                
        except Exception as e:
            logger.error(f"Failed to send high-risk alert: {e}")
    
    def _queue_for_manual_review(self, notification_data: Dict):
        """Queue entity for manual review"""
        try:
            review_queue_url = os.getenv('MANUAL_REVIEW_QUEUE_URL')
            if review_queue_url:
                review_request = {
                    'review_type': 'RISK_ASSESSMENT_REVIEW',
                    'entity_name': notification_data.get('entity_name'),
                    'record_id': notification_data.get('record_id'),
                    'risk_level': notification_data.get('risk_level'),
                    'requires_review_reason': 'Low confidence or high risk',
                    'queued_at': datetime.now().isoformat()
                }
                
                self.sqs.send_message(
                    QueueUrl=review_queue_url,
                    MessageBody=json.dumps(review_request)
                )
                
                logger.info(f"Queued {notification_data.get('entity_name')} for manual review")
                
        except Exception as e:
            logger.error(f"Failed to queue for manual review: {e}")

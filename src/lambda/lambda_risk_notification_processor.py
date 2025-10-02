#!/usr/bin/env python3
"""
Risk Notification Processor Lambda Function
Processes risk assessment notifications from SQS queue
"""

import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import shared modules
try:
    from shared.production_security_fixes import SecurityManager, create_secure_response
    from shared.production_monitoring import CloudWatchMetrics
    from shared.risk_output_service import RiskNotificationProcessor, RiskOutputService
except ImportError:
    logger.error("Failed to import shared modules. Ensure they are in the deployment package.")
    raise

def lambda_handler(event, context):
    """
    AWS Lambda handler for processing risk notifications from SQS
    
    Args:
        event: SQS event containing risk notification messages
        context: Lambda context object
        
    Returns:
        Processing results
    """
    
    # Initialize components
    security_manager = SecurityManager()
    metrics = CloudWatchMetrics()
    notification_processor = RiskNotificationProcessor()
    risk_output_service = RiskOutputService()
    
    try:
        logger.info("Risk Notification Processor Lambda started")
        
        # Security validation
        security_manager.validate_request(event, context)
        
        processed_count = 0
        failed_count = 0
        
        # Process SQS records
        if 'Records' in event:
            for record in event['Records']:
                try:
                    logger.info(f"Processing SQS message: {record.get('messageId', 'unknown')}")
                    
                    # Process the notification
                    success = notification_processor.process_notification(record)
                    
                    if success:
                        processed_count += 1
                        metrics.increment_counter('risk_notifications_processed')
                    else:
                        failed_count += 1
                        metrics.increment_counter('risk_notification_processing_failures')
                        
                except Exception as e:
                    logger.error(f"Failed to process SQS record: {e}")
                    failed_count += 1
                    metrics.increment_counter('risk_notification_processing_errors')
        
        # Log processing summary
        logger.info(f"Risk notification processing completed. "
                   f"Processed: {processed_count}, Failed: {failed_count}")
        
        # Record metrics
        metrics.record_custom_metric('RiskNotificationsProcessed', processed_count, 'Count')
        metrics.record_custom_metric('RiskNotificationFailures', failed_count, 'Count')
        
        return create_secure_response(200, {
            'message': 'Risk notifications processed successfully',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in risk notification processor: {e}")
        metrics.increment_counter('risk_notification_processor_errors')
        return create_secure_response(500, {
            'error': 'Internal server error',
            'timestamp': datetime.now().isoformat()
        })

def get_risk_dashboard_data(event, context):
    """
    Lambda handler for retrieving risk dashboard data
    
    Args:
        event: API Gateway event with query parameters
        context: Lambda context object
        
    Returns:
        Risk assessment data for dashboard
    """
    
    try:
        # Initialize services
        risk_output_service = RiskOutputService()
        metrics = CloudWatchMetrics()
        
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        entity_name = query_params.get('entity_name')
        risk_level = query_params.get('risk_level')
        limit = int(query_params.get('limit', 50))
        
        # Get risk assessments
        risk_assessments = risk_output_service.get_risk_assessments(
            entity_name=entity_name,
            risk_level=risk_level,
            limit=limit
        )
        
        # Calculate summary statistics
        summary_stats = calculate_risk_summary(risk_assessments)
        
        # Record metrics
        metrics.record_custom_metric('RiskDashboardRequests', 1, 'Count')
        metrics.record_custom_metric('RiskAssessmentsRetrieved', len(risk_assessments), 'Count')
        
        response_data = {
            'risk_assessments': risk_assessments,
            'summary_stats': summary_stats,
            'total_count': len(risk_assessments),
            'filters_applied': {
                'entity_name': entity_name,
                'risk_level': risk_level,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return create_secure_response(200, response_data)
        
    except Exception as e:
        logger.error(f"Error retrieving risk dashboard data: {e}")
        return create_secure_response(500, {
            'error': 'Failed to retrieve risk data',
            'timestamp': datetime.now().isoformat()
        })

def calculate_risk_summary(risk_assessments: List[Dict]) -> Dict:
    """
    Calculate summary statistics for risk assessments
    
    Args:
        risk_assessments: List of risk assessment records
        
    Returns:
        Summary statistics
    """
    if not risk_assessments:
        return {
            'total_assessments': 0,
            'risk_level_distribution': {},
            'average_risk_score': 0.0,
            'high_risk_count': 0,
            'requires_review_count': 0
        }
    
    # Initialize counters
    risk_level_counts = {}
    total_risk_score = 0.0
    high_risk_count = 0
    requires_review_count = 0
    
    # Process each assessment
    for assessment in risk_assessments:
        risk_level = assessment.get('risk_level', 'UNKNOWN')
        risk_score = float(assessment.get('overall_risk_score', 0.0))
        
        # Count risk levels
        risk_level_counts[risk_level] = risk_level_counts.get(risk_level, 0) + 1
        
        # Sum risk scores
        total_risk_score += risk_score
        
        # Count high-risk entities
        if risk_level in ['HIGH', 'CRITICAL'] or risk_score >= 0.8:
            high_risk_count += 1
        
        # Count entities requiring review
        confidence = float(assessment.get('confidence_level', 1.0))
        if risk_level in ['HIGH', 'CRITICAL'] or confidence < 0.6:
            requires_review_count += 1
    
    # Calculate averages
    average_risk_score = total_risk_score / len(risk_assessments) if risk_assessments else 0.0
    
    return {
        'total_assessments': len(risk_assessments),
        'risk_level_distribution': risk_level_counts,
        'average_risk_score': round(average_risk_score, 3),
        'high_risk_count': high_risk_count,
        'requires_review_count': requires_review_count,
        'high_risk_percentage': round((high_risk_count / len(risk_assessments)) * 100, 1),
        'review_required_percentage': round((requires_review_count / len(risk_assessments)) * 100, 1)
    }

def manual_review_handler(event, context):
    """
    Lambda handler for manual review queue processing
    
    Args:
        event: SQS event from manual review queue
        context: Lambda context object
        
    Returns:
        Processing results
    """
    
    try:
        logger.info("Manual Review Handler Lambda started")
        
        processed_count = 0
        
        # Process manual review requests
        if 'Records' in event:
            for record in event['Records']:
                try:
                    # Parse review request
                    if isinstance(record.get('body'), str):
                        review_request = json.loads(record['body'])
                    else:
                        review_request = record.get('body', {})
                    
                    logger.info(f"Processing manual review for entity: "
                               f"{review_request.get('entity_name', 'Unknown')}")
                    
                    # Here you would integrate with your manual review system
                    # For now, we'll just log the request
                    
                    review_data = {
                        'entity_name': review_request.get('entity_name'),
                        'record_id': review_request.get('record_id'),
                        'risk_level': review_request.get('risk_level'),
                        'review_reason': review_request.get('requires_review_reason'),
                        'queued_at': review_request.get('queued_at'),
                        'processed_at': datetime.now().isoformat(),
                        'status': 'PENDING_MANUAL_REVIEW'
                    }
                    
                    # Store in review tracking system (implement as needed)
                    logger.info(f"Manual review queued: {json.dumps(review_data, indent=2)}")
                    
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process manual review request: {e}")
        
        logger.info(f"Manual review processing completed. Processed: {processed_count}")
        
        return create_secure_response(200, {
            'message': 'Manual review requests processed',
            'processed_count': processed_count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in manual review handler: {e}")
        return create_secure_response(500, {
            'error': 'Manual review processing failed',
            'timestamp': datetime.now().isoformat()
        })

# 🔍 Entity Screening Guide

## Overview

The Entity Screening system provides comprehensive screening capabilities for financial crimes and corruption using predefined keyword lists. This guide covers the implementation, usage, and integration of entity screening functionality.

---

## 🎯 **Keywords Coverage**

### **1. Financial Crimes & Fraud (10 keywords)**
- fraud
- scam
- Ponzi
- embezzlement
- insider trading
- accounting irregularities
- money laundering
- misappropriation
- kickbacks
- shell company

### **2. Corruption & Bribery (8 keywords)**
- bribery
- corruption
- graft
- undue influence
- facilitation payment
- procurement fraud
- nepotism
- political donation scandal

**Total: 18 screening keywords across 2 categories**

---

## 🏗️ **Architecture Components**

### **Core Components**
1. **`EntityScreeningKeywords`** - Keyword management system
2. **`lambda_entity_screening_service.py`** - Dedicated screening service
3. **Enhanced search services** - Integration with existing services
4. **Orchestrator integration** - Routing for entity screening

### **File Structure**
```
src/
├── shared/
│   └── entity_screening_keywords.py    # Keyword management system
├── lambda/
│   ├── lambda_entity_screening_service.py  # Dedicated screening service
│   ├── lambda_search_service_secure.py     # Enhanced with screening
│   └── lambda_orchestrator_secure.py       # Routing support
└── entity_screening_demo.py            # Demo and examples
```

---

## 🚀 **Usage Examples**

### **1. Direct Keyword Management**

```python
from shared.entity_screening_keywords import EntityScreeningKeywords, ScreeningCategory

# Initialize keyword manager
keywords_manager = EntityScreeningKeywords()

# Get all financial crimes keywords
financial_keywords = keywords_manager.get_keywords_list(ScreeningCategory.FINANCIAL_CRIMES)
print(financial_keywords)
# Output: ['accounting irregularities', 'embezzlement', 'fraud', ...]

# Generate entity screening queries
entity_name = "Acme Corporation"
queries = keywords_manager.generate_entity_search_queries(
    entity_name, 
    ScreeningCategory.FINANCIAL_CRIMES, 
    max_queries=5
)
print(queries)
# Output: ['"Acme Corporation" fraud', 'Acme Corporation fraud', ...]
```

### **2. Comprehensive Entity Screening**

```python
# Generate queries for all categories
comprehensive_queries = keywords_manager.generate_comprehensive_search_queries(
    "Target Company", 
    queries_per_category=3
)

for category, queries in comprehensive_queries.items():
    print(f"{category}: {queries}")
```

### **3. Custom Keyword Management**

```python
# Add custom keywords
keywords_manager.add_custom_keyword("cryptocurrency fraud", ScreeningCategory.FINANCIAL_CRIMES)

# Export keywords for backup
exported = keywords_manager.export_keywords()

# Get statistics
stats = keywords_manager.get_keyword_statistics()
print(stats)  # {'financial_crimes': 11, 'corruption_bribery': 8, 'total': 19}
```

---

## 📡 **API Usage**

### **1. Enhanced Search Service**

**Endpoint**: `POST /search`

```json
{
  "entity_name": "Suspicious Company Ltd",
  "use_entity_screening": true,
  "screening_category": "financial_crimes",
  "num_results": 10,
  "process_with_llm": true,
  "store_results": true
}
```

**Response**:
```json
{
  "success": true,
  "query": "\"Suspicious Company Ltd\" fraud",
  "results": [...],
  "total_count": 10,
  "stored_in_database": true,
  "llm_processing_triggered": true
}
```

### **2. Dedicated Entity Screening Service**

**Function**: `entity-screening-service`

```json
{
  "entity_name": "Target Corporation",
  "comprehensive_screening": true,
  "queries_per_category": 3,
  "store_results": true,
  "process_with_llm": true
}
```

**Response**:
```json
{
  "entity_name": "Target Corporation",
  "screening_results": {
    "financial_crimes": [...],
    "corruption_bribery": [...],
    "mixed": [...]
  },
  "screening_summary": {
    "total_categories_screened": 3,
    "total_results_found": 45,
    "categories_with_results": ["financial_crimes", "corruption_bribery"],
    "processing_time_seconds": 12.5
  }
}
```

### **3. Orchestrator with Entity Screening**

**Endpoint**: `POST /search`

```json
{
  "processing_mode": "async",
  "use_entity_screening": true,
  "entity_name": "Global Industries Inc",
  "screening_categories": ["financial_crimes", "corruption_bribery"],
  "comprehensive_screening": true,
  "process_with_llm": true
}
```

---

## 🔧 **Integration Patterns**

### **Pattern 1: Simple Entity Screening**
```python
# Quick screening with existing search service
payload = {
    "entity_name": "Company Name",
    "use_entity_screening": True,
    "screening_category": "all",
    "num_results": 10
}
```

### **Pattern 2: Comprehensive Screening**
```python
# Full screening across all categories
payload = {
    "entity_name": "Company Name",
    "comprehensive_screening": True,
    "queries_per_category": 5,
    "store_results": True
}
```

### **Pattern 3: Category-Specific Screening**
```python
# Target specific risk categories
payload = {
    "entity_name": "Company Name",
    "screening_categories": ["financial_crimes"],
    "queries_per_category": 3
}
```

---

## 🎛️ **Configuration Options**

### **Search Service Configuration**
- `use_entity_screening`: Enable entity screening mode
- `entity_name`: Target entity name (required for screening)
- `screening_category`: Category to screen (`financial_crimes`, `corruption_bribery`, `all`)

### **Entity Screening Service Configuration**
- `comprehensive_screening`: Screen all categories with mixed queries
- `screening_categories`: List of specific categories to screen
- `queries_per_category`: Number of queries per category (default: 5)

### **Processing Options**
- `store_results`: Store results in DynamoDB (default: true)
- `process_with_llm`: Trigger LLM analysis (default: false)
- `callback_topic`: SNS topic for async LLM processing

---

## 📊 **Monitoring & Metrics**

### **Custom CloudWatch Metrics**
- `EntityScreeningRequests`: Number of screening requests
- `EntityScreeningResults`: Total results found
- `EntityScreeningTime`: Processing time per request
- `EntityScreeningErrors`: Error count by type

### **Health Check Endpoints**
```bash
# Entity screening service health
curl https://api-gateway-url/entity-screening/health

# Response includes keyword statistics
{
  "service": "entity-screening-service",
  "status": "healthy",
  "keyword_statistics": {
    "financial_crimes": 10,
    "corruption_bribery": 8,
    "total": 18
  }
}
```

---

## 🧪 **Testing**

### **Run Demo Script**
```bash
cd src/
python entity_screening_demo.py
```

### **Unit Tests**
```python
# Test keyword generation
def test_entity_screening_keywords():
    keywords_manager = EntityScreeningKeywords()
    
    # Test financial crimes keywords
    financial = keywords_manager.get_keywords_list(ScreeningCategory.FINANCIAL_CRIMES)
    assert len(financial) == 10
    assert "fraud" in financial
    
    # Test query generation
    queries = keywords_manager.generate_entity_search_queries("Test Corp", max_queries=3)
    assert len(queries) <= 3
    assert "Test Corp" in queries[0]
```

### **Integration Tests**
```python
# Test Lambda function integration
def test_entity_screening_service():
    event = {
        "entity_name": "Test Company",
        "comprehensive_screening": True,
        "queries_per_category": 2
    }
    
    # Mock the Lambda handler
    result = lambda_handler(event, mock_context)
    assert result['statusCode'] == 200
```

---

## 🔒 **Security Considerations**

### **Data Privacy**
- Entity names are truncated in logs for privacy
- Search queries are sanitized and validated
- Results are stored with TTL for automatic cleanup

### **Rate Limiting**
- Built-in delays between API calls (0.5 seconds)
- Configurable query limits per category
- Monitoring for unusual request patterns

### **Access Control**
- Same IAM permissions as existing services
- Secrets Manager integration for API keys
- Secure parameter validation

---

## 🚀 **Deployment**

### **1. Update CloudFormation Template**
Add the entity screening service to your infrastructure:

```yaml
EntityScreeningFunction:
  Type: AWS::Lambda::Function
  Properties:
    FunctionName: entity-screening-service
    Runtime: python3.11
    Handler: lambda_entity_screening_service.lambda_handler
    Environment:
      Variables:
        RESULTS_TABLE: !Ref ResultsTable
        LLM_PROCESSING_TOPIC: !Ref LLMProcessingTopic
```

### **2. Update CI/CD Pipeline**
Add entity screening service to the deployment pipeline:

```bash
# Package entity screening service
mkdir entity-screening-service
cp src/lambda/lambda_entity_screening_service.py entity-screening-service/lambda_function.py
cp src/shared/*.py entity-screening-service/
cd entity-screening-service && zip -r ../entity-screening-service.zip .
```

### **3. Environment Variables**
```bash
# Add to Lambda environment variables
ENTITY_SCREENING_FUNCTION_NAME=entity-screening-service
```

---

## 📈 **Performance Optimization**

### **Query Optimization**
- Limit queries per category (default: 5)
- Use targeted categories instead of comprehensive screening
- Implement result caching for repeated entities

### **API Rate Limiting**
- Built-in 0.5-second delays between requests
- Configurable batch sizes
- Exponential backoff for failures

### **Cost Management**
- TTL-based cleanup of old results
- Efficient query generation
- Optional result storage

---

## 🔄 **Future Enhancements**

### **Planned Features**
1. **Dynamic Keyword Updates**: Real-time keyword management
2. **ML-Based Scoring**: Risk scoring based on results
3. **Batch Processing**: Multiple entity screening
4. **Custom Categories**: User-defined keyword categories
5. **Historical Analysis**: Trend analysis over time

### **Integration Opportunities**
1. **Webhook Notifications**: Real-time alerts for high-risk entities
2. **Dashboard Integration**: Visual screening results
3. **Export Capabilities**: PDF/Excel report generation
4. **API Rate Optimization**: Intelligent query batching

---

## 📞 **Support**

### **Documentation**
- `entity_screening_demo.py`: Interactive examples
- `src/shared/entity_screening_keywords.py`: Full API documentation
- Unit tests in `src/tests/test_suite.py`

### **Troubleshooting**
- Check CloudWatch logs for detailed error messages
- Verify API key configuration in Secrets Manager
- Monitor rate limiting and quota usage
- Test with demo script for validation

**The entity screening system is production-ready and fully integrated with your existing search agent architecture!** 🎯

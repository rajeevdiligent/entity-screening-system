# 🏗️ Entity Screening System - Complete Architecture Flow

## 🎯 100% Functional System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           🌐 CLIENT REQUEST FLOW                                        │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    📱 Client Application
         │
         │ POST /prod/search
         │ {
         │   "query": "Wells Fargo fraud",
         │   "num_results": 3,
         │   "enable_llm_processing": true
         │ }
         ▼
    ┌─────────────────────┐
    │   🚪 API Gateway    │ ◄─── HTTPS/TLS Encryption
    │  (REST API)         │      Security Headers
    │                     │      Rate Limiting
    └─────────────────────┘
         │
         │ Lambda Proxy Integration
         │ event['body'] = JSON payload
         ▼

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🔍 SEARCH SERVICE LAYER                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐
    │  🔍 Search Service  │ ◄─── entity-search-service
    │    Lambda Function  │      Runtime: Python 3.11
    │                     │      Memory: 256MB, Timeout: 30s
    │  ┌─────────────────┐│      Handler: lambda_search_service_secure.lambda_handler
    │  │ Input Validator ││ ◄─── Validates query, num_results
    │  └─────────────────┘│      Security checks
    │  ┌─────────────────┐│
    │  │Security Manager ││ ◄─── AWS Secrets Manager integration
    │  └─────────────────┘│      API key retrieval
    │  ┌─────────────────┐│
    │  │ Serper API Call ││ ◄─── External search via requests library
    │  └─────────────────┘│      Google search results
    └─────────────────────┘
         │                │
         │ Search Results │ SNS Message (if LLM enabled)
         ▼                ▼
    ┌─────────────────────┐    ┌─────────────────────┐
    │  💾 DynamoDB        │    │  📢 SNS Topic       │
    │  Storage            │    │  (LLM Processing)   │
    │                     │    │                     │
    │ search-analysis-    │    │ llm-processing-     │
    │ results table       │    │ requests            │
    │                     │    │                     │
    │ ┌─────────────────┐ │    └─────────────────────┘
    │ │ Search Results  │ │              │
    │ │ - query         │ │              │ Async Trigger
    │ │ - results[]     │ │              ▼
    │ │ - timestamp     │ │    ┌─────────────────────┐
    │ │ - query_hash    │ │    │  🧠 LLM Service     │
    │ └─────────────────┘ │    │    Lambda Function  │
    └─────────────────────┘    │                     │
         │                     │  Runtime: Python 3.11
         │ Immediate Response  │  Memory: 512MB
         ▼                     │  Timeout: 300s
    ┌─────────────────────┐    │                     │
    │  📤 API Response    │    │ ┌─────────────────┐ │
    │                     │    │ │ Amazon Nova LLM │ │ ◄─── Bedrock Integration
    │ {                   │    │ │ Risk Analysis   │ │      amazon.nova-micro-v1:0
    │   "query": "...",   │    │ └─────────────────┘ │      Comprehensive risk scoring
    │   "results": [...], │    │ ┌─────────────────┐ │
    │   "total_count": 3, │    │ │ Risk Calculator │ │ ◄─── Multi-dimensional scoring
    │   "llm_processing_  │    │ │ Float→Decimal   │ │      Financial, Corruption,
    │   triggered": true, │    │ └─────────────────┘ │      Regulatory, Reputational
    │   "stored_in_       │    └─────────────────────┘
    │   database": true   │              │
    │ }                   │              │ Risk Analysis Results
    └─────────────────────┘              ▼
                                ┌─────────────────────┐
                                │  💾 DynamoDB        │
                                │  Risk Storage       │
                                │                     │
                                │ ┌─────────────────┐ │
                                │ │ LLM Analysis    │ │
                                │ │ - overall_risk  │ │
                                │ │ - risk_level    │ │
                                │ │ - financial_    │ │
                                │ │   crimes_risk   │ │
                                │ │ - corruption_   │ │
                                │ │   risk          │ │
                                │ │ - regulatory_   │ │
                                │ │   risk          │ │
                                │ │ - reputational_ │ │
                                │ │   risk          │ │
                                │ │ - key_findings  │ │
                                │ │ - confidence    │ │
                                │ └─────────────────┘ │
                                └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🔐 SECURITY & MONITORING LAYER                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
    │  🔐 AWS Secrets     │    │  📊 CloudWatch      │    │  🛡️ Security        │
    │     Manager         │    │     Monitoring      │    │    Features         │
    │                     │    │                     │    │                     │
    │ entity-screening/   │    │ ┌─────────────────┐ │    │ ┌─────────────────┐ │
    │ serper-api-key      │    │ │ Lambda Metrics  │ │    │ │ Input Validation│ │
    │                     │    │ │ - Duration      │ │    │ │ XSS Protection  │ │
    │ Encrypted storage   │    │ │ - Memory Usage  │ │    │ │ CORS Headers    │ │
    │ IAM role access     │    │ │ - Error Rates   │ │    │ │ Rate Limiting   │ │
    └─────────────────────┘    │ └─────────────────┘ │    │ └─────────────────┘ │
                               │ ┌─────────────────┐ │    │ ┌─────────────────┐ │
                               │ │ API Gateway     │ │    │ │ Secure Response │ │
                               │ │ - Request Count │ │    │ │ Error Handling  │ │
                               │ │ - Latency       │ │    │ │ No Data Leakage │ │
                               │ │ - 4xx/5xx Errors│ │    │ └─────────────────┘ │
                               │ └─────────────────┘ │    └─────────────────────┘
                               └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🌍 EXTERNAL INTEGRATIONS                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
    │  🔍 Serper API      │    │  🧠 Amazon Bedrock  │    │  💾 AWS DynamoDB    │
    │  (Google Search)    │    │  (Nova LLM)         │    │  (Data Storage)     │
    │                     │    │                     │    │                     │
    │ https://google.     │    │ amazon.nova-micro-  │    │ search-analysis-    │
    │ serper.dev/search   │    │ v1:0                │    │ results             │
    │                     │    │                     │    │                     │
    │ Real-time search    │    │ Risk analysis       │    │ NoSQL database      │
    │ 3 results per query │    │ JSON response       │    │ Auto-scaling        │
    │ Snippet extraction  │    │ Multi-dimensional   │    │ TTL: 30 days        │
    └─────────────────────┘    │ scoring             │    │ Float→Decimal       │
                               └─────────────────────┘    │ conversion          │
                                                          └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        📊 DATA FLOW SUMMARY                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

1. 📱 Client → 🚪 API Gateway → 🔍 Search Service
   ├─ Input validation & security checks
   ├─ Serper API call for search results
   └─ Immediate response to client

2. 🔍 Search Service → 💾 DynamoDB (Search Results)
   ├─ Store raw search data
   ├─ Generate query hash
   └─ Set TTL for cleanup

3. 🔍 Search Service → 📢 SNS → 🧠 LLM Service (Async)
   ├─ Trigger if enable_llm_processing=true
   ├─ Pass search results for analysis
   └─ Non-blocking operation

4. 🧠 LLM Service → 🧠 Amazon Nova → 💾 DynamoDB (Risk Analysis)
   ├─ Comprehensive risk scoring
   ├─ Multi-dimensional analysis
   ├─ Float→Decimal conversion
   └─ Store detailed risk assessment

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🎯 SYSTEM CAPABILITIES                                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘

✅ SEARCH CAPABILITIES:
   • Real-time Google search via Serper API
   • Configurable result count (1-10)
   • Query validation and sanitization
   • Response caching and optimization

✅ RISK ANALYSIS:
   • Financial crimes detection (fraud, money laundering)
   • Corruption screening (bribery, graft)
   • Regulatory compliance checking
   • Reputational risk assessment
   • Confidence scoring (0-100%)

✅ TECHNICAL FEATURES:
   • Async processing for performance
   • Auto-scaling Lambda functions
   • Secure secret management
   • Comprehensive error handling
   • CloudWatch monitoring & alerting

✅ SECURITY MEASURES:
   • HTTPS/TLS encryption
   • Input validation & sanitization
   • XSS/CSRF protection
   • Rate limiting
   • Secure headers (HSTS, CSP, etc.)

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🚀 DEPLOYMENT STATUS                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

🎉 SYSTEM STATUS: 100% OPERATIONAL

✅ All Lambda functions deployed and working
✅ Bedrock permissions configured correctly
✅ DynamoDB float handling resolved
✅ End-to-end testing completed successfully
✅ Security measures implemented and verified
✅ Monitoring and logging operational

🏆 READY FOR PRODUCTION USE!

API Endpoint: https://2glcobonoc.execute-api.us-east-1.amazonaws.com/prod/search
Region: us-east-1
Account: 891067072053
```

## 🔄 **Request/Response Flow Example**

### **Input Request:**
```json
POST /prod/search
{
  "query": "Wells Fargo regulatory violations",
  "num_results": 3,
  "enable_llm_processing": true
}
```

### **Immediate Response:**
```json
{
  "query": "Wells Fargo regulatory violations",
  "results": [
    {
      "title": "Wells Fargo Regulatory Issues",
      "url": "https://example.com/wells-fargo-violations",
      "snippet": "Wells Fargo faces regulatory scrutiny...",
      "position": 1
    }
  ],
  "total_count": 3,
  "timestamp": "2025-10-02T09:46:30.216529",
  "llm_processing_triggered": true,
  "stored_in_database": true,
  "storage_info": {
    "query_hash": "abc123...",
    "storage_timestamp": "2025-10-02T09:46:30.621299"
  }
}
```

### **Async LLM Analysis (stored in DynamoDB):**
```json
{
  "overall_risk_score": 75.5,
  "risk_level": "HIGH",
  "financial_crimes_risk": 80.0,
  "corruption_risk": 65.0,
  "regulatory_risk": 85.0,
  "reputational_risk": 70.0,
  "key_findings": ["Regulatory violations", "Settlement history"],
  "confidence_level": 92.5
}
```

---

**🎯 This architecture represents a fully functional, production-ready entity screening system with comprehensive risk analysis capabilities!**

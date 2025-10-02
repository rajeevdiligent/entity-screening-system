# 🏗️ Entity Screening System - Complete Architecture Flow

## 🎯 100% Functional System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           🌐 CLIENT REQUEST FLOW                                        │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    📱 Client Application
         │
         │ POST /prod/search          │ POST /prod/GDCsearch
         │ {                          │ {
         │   "query": "Wells Fargo    │   "query": "Wells Fargo fraud",
         │            fraud",         │   "index": "gdc-entities",
         │   "num_results": 3,        │   "size": 10,
         │   "enable_llm_processing": │   "enable_llm_processing": true
         │            true            │ }
         │ }                          │
         ▼                            ▼
    ┌─────────────────────────────────────────┐
    │         🚪 API Gateway (REST API)        │ ◄─── HTTPS/TLS Encryption
    │                                         │      Security Headers
    │  /prod/search     │  /prod/GDCsearch    │      Rate Limiting
    │  (Serper API)     │  (OpenSearch)       │      CORS Configuration
    └─────────────────────────────────────────┘
         │                            │
         │ Lambda Proxy Integration   │ Lambda Proxy Integration
         │ event['body'] = JSON       │ event['body'] = JSON
         ▼                            ▼

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        🔍 DUAL SEARCH SERVICE LAYER                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────┐              ┌─────────────────────┐
    │  🔍 Serper Search   │              │  🔍 GDC Search      │
    │    Service Lambda   │              │    Service Lambda   │
    │                     │              │                     │
    │ entity-search-      │              │ entity-gdc-search-  │
    │ service             │              │ service             │
    │                     │              │                     │
    │ Runtime: Python 3.11│              │ Runtime: Python 3.11│
    │ Memory: 256MB       │              │ Memory: 512MB       │
    │ Timeout: 30s        │              │ Timeout: 60s        │
    │                     │              │                     │
    │ ┌─────────────────┐ │              │ ┌─────────────────┐ │
    │ │ Input Validator │ │ ◄─── Query   │ │ Input Validator │ │ ◄─── Query
    │ └─────────────────┘ │      Security│ └─────────────────┘ │      Security
    │ ┌─────────────────┐ │      Checks  │ ┌─────────────────┐ │      Checks
    │ │Security Manager │ │              │ │Security Manager │ │
    │ └─────────────────┘ │              │ └─────────────────┘ │
    │ ┌─────────────────┐ │              │ ┌─────────────────┐ │
    │ │ Serper API Call │ │ ◄─── Google  │ │OpenSearch Client│ │ ◄─── GDC
    │ │ (External)      │ │      Search  │ │ (AWS Service)   │ │      Index
    │ └─────────────────┘ │              │ └─────────────────┘ │
    └─────────────────────┘              └─────────────────────┘
         │                                        │
         │ Serper Results                         │ OpenSearch Results
         ▼                                        ▼
         │                                        │
         │ Both services store results & trigger LLM processing
         ▼                                        ▼
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
    │  🔍 Serper API      │    │  🔍 AWS OpenSearch  │    │  🧠 Amazon Bedrock  │
    │  (Google Search)    │    │  (GDC Index)        │    │  (Nova LLM)         │
    │                     │    │                     │    │                     │
    │ https://google.     │    │ GDC Entity Index    │    │ amazon.nova-micro-  │
    │ serper.dev/search   │    │ Elasticsearch API   │    │ v1:0                │
    │                     │    │                     │    │                     │
    │ Real-time search    │    │ Structured search   │    │ Risk analysis       │
    │ 3 results per query │    │ Entity matching     │    │ JSON response       │
    │ Snippet extraction  │    │ Relevance scoring   │    │ Multi-dimensional   │
    │ Web content         │    │ Faceted search      │    │ scoring             │
    └─────────────────────┘    │ Full-text queries   │    └─────────────────────┘
                               └─────────────────────┘
    
    ┌─────────────────────┐
    │  💾 AWS DynamoDB    │
    │  (Data Storage)     │
    │                     │
    │ search-analysis-    │
    │ results             │
    │                     │
    │ NoSQL database      │
    │ Auto-scaling        │
    │ TTL: 30 days        │
    │ Float→Decimal       │
    │ conversion          │
    └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        📊 DATA FLOW SUMMARY                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

1. 📱 Client → 🚪 API Gateway → 🔍 Dual Search Services
   ├─ /prod/search → Serper API (Google Search)
   │  ├─ Input validation & security checks
   │  ├─ External API call for web results
   │  └─ Immediate response to client
   └─ /prod/GDCsearch → OpenSearch (GDC Index)
      ├─ Input validation & security checks
      ├─ AWS OpenSearch query execution
      └─ Structured entity data response

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

✅ DUAL SEARCH CAPABILITIES:
   • Real-time Google search via Serper API (/prod/search)
   • GDC entity search via AWS OpenSearch (/prod/GDCsearch)
   • Configurable result count and pagination
   • Query validation and sanitization
   • Response caching and optimization
   • Structured vs. unstructured data sources

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

## 🔄 **Dual Endpoint Request/Response Examples**

### **🔍 Serper API Search (Google):**
```json
POST /prod/search
{
  "query": "Wells Fargo regulatory violations",
  "num_results": 3,
  "enable_llm_processing": true
}
```

### **🔍 GDC OpenSearch (Entity Index):**
```json
POST /prod/GDCsearch
{
  "query": "Wells Fargo regulatory violations",
  "index": "gdc-entities",
  "size": 10,
  "enable_llm_processing": true,
  "filters": {
    "entity_type": "financial_institution",
    "jurisdiction": "US"
  }
}
```

### **🔍 Serper Response (Web Results):**
```json
{
  "query": "Wells Fargo regulatory violations",
  "source": "serper_api",
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
  "stored_in_database": true
}
```

### **🔍 GDC OpenSearch Response (Entity Data):**
```json
{
  "query": "Wells Fargo regulatory violations",
  "source": "gdc_opensearch",
  "results": [
    {
      "entity_id": "WFC_US_BANK_001",
      "entity_name": "Wells Fargo & Company",
      "entity_type": "financial_institution",
      "jurisdiction": "US",
      "risk_indicators": ["regulatory_violations", "consumer_complaints"],
      "last_updated": "2025-10-01T12:00:00Z",
      "relevance_score": 0.95
    }
  ],
  "total_hits": 15,
  "timestamp": "2025-10-02T09:46:30.216529",
  "llm_processing_triggered": true,
  "stored_in_database": true
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

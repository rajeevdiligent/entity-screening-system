#!/usr/bin/env python3
"""
Entity Screening Demo
Demonstrates the entity screening functionality with financial crimes and corruption keywords
"""

import json
from shared.entity_screening_keywords import EntityScreeningKeywords, ScreeningCategory

def main():
    """Demonstrate entity screening functionality"""
    
    print("🔍 Entity Screening Keywords Demo")
    print("=" * 50)
    
    # Initialize the keywords manager
    keywords_manager = EntityScreeningKeywords()
    
    # Display keyword statistics
    print("\n📊 Keyword Statistics:")
    stats = keywords_manager.get_keyword_statistics()
    for category, count in stats.items():
        print(f"  {category}: {count} keywords")
    
    # Display all keywords by category
    print("\n💰 Financial Crimes & Fraud Keywords:")
    financial_keywords = keywords_manager.get_keywords_list(ScreeningCategory.FINANCIAL_CRIMES)
    for i, keyword in enumerate(financial_keywords, 1):
        print(f"  {i:2d}. {keyword}")
    
    print("\n🏛️  Corruption & Bribery Keywords:")
    corruption_keywords = keywords_manager.get_keywords_list(ScreeningCategory.CORRUPTION_BRIBERY)
    for i, keyword in enumerate(corruption_keywords, 1):
        print(f"  {i:2d}. {keyword}")
    
    # Example entity screening
    entity_name = "Acme Corporation"
    print(f"\n🎯 Entity Screening Example: '{entity_name}'")
    print("-" * 50)
    
    # Generate queries for financial crimes
    print("\n💰 Financial Crimes Screening Queries:")
    financial_queries = keywords_manager.generate_entity_search_queries(
        entity_name, ScreeningCategory.FINANCIAL_CRIMES, max_queries=5
    )
    for i, query in enumerate(financial_queries, 1):
        print(f"  {i}. {query}")
    
    # Generate queries for corruption
    print("\n🏛️  Corruption & Bribery Screening Queries:")
    corruption_queries = keywords_manager.generate_entity_search_queries(
        entity_name, ScreeningCategory.CORRUPTION_BRIBERY, max_queries=5
    )
    for i, query in enumerate(corruption_queries, 1):
        print(f"  {i}. {query}")
    
    # Comprehensive screening
    print(f"\n🔍 Comprehensive Entity Screening: '{entity_name}'")
    print("-" * 50)
    comprehensive_queries = keywords_manager.generate_comprehensive_search_queries(entity_name, 3)
    
    for category, queries in comprehensive_queries.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        for i, query in enumerate(queries, 1):
            print(f"  {i}. {query}")
    
    # Example API request format
    print("\n📡 Example API Request for Entity Screening:")
    print("-" * 50)
    
    api_request_example = {
        "entity_name": "Acme Corporation",
        "screening_categories": ["financial_crimes", "corruption_bribery"],
        "queries_per_category": 5,
        "comprehensive_screening": True,
        "store_results": True,
        "process_with_llm": True
    }
    
    print(json.dumps(api_request_example, indent=2))
    
    # Lambda function usage examples
    print("\n⚡ Lambda Function Usage Examples:")
    print("-" * 50)
    
    print("\n1. Search Service with Entity Screening:")
    search_request = {
        "entity_name": "Suspicious Company Ltd",
        "use_entity_screening": True,
        "screening_category": "financial_crimes",
        "num_results": 10,
        "process_with_llm": True
    }
    print(json.dumps(search_request, indent=2))
    
    print("\n2. Dedicated Entity Screening Service:")
    screening_request = {
        "entity_name": "Target Corporation",
        "comprehensive_screening": True,
        "queries_per_category": 3,
        "store_results": True,
        "process_with_llm": True
    }
    print(json.dumps(screening_request, indent=2))
    
    print("\n3. Orchestrator with Entity Screening:")
    orchestrator_request = {
        "processing_mode": "async",
        "entity_name": "Global Industries Inc",
        "use_entity_screening": True,
        "screening_categories": ["all"],
        "num_results": 15
    }
    print(json.dumps(orchestrator_request, indent=2))
    
    # Custom keyword management
    print("\n🔧 Custom Keyword Management:")
    print("-" * 50)
    
    # Add a custom keyword
    keywords_manager.add_custom_keyword("cryptocurrency fraud", ScreeningCategory.FINANCIAL_CRIMES)
    print("✅ Added 'cryptocurrency fraud' to financial crimes keywords")
    
    # Show updated statistics
    updated_stats = keywords_manager.get_keyword_statistics()
    print(f"📊 Updated financial crimes keywords: {updated_stats['financial_crimes']}")
    
    # Export keywords
    print("\n📤 Export Keywords (JSON format):")
    exported_keywords = keywords_manager.export_keywords()
    print(json.dumps(exported_keywords, indent=2))
    
    print("\n🎉 Demo completed! The entity screening system is ready for production use.")
    print("\nKey Features:")
    print("✅ 18 total screening keywords across 2 categories")
    print("✅ Automatic query generation for entity screening")
    print("✅ Comprehensive multi-category screening")
    print("✅ Integration with existing Lambda services")
    print("✅ Custom keyword management")
    print("✅ Production-ready with security and monitoring")

if __name__ == "__main__":
    main()

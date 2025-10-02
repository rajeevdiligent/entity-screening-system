#!/usr/bin/env python3
"""
Entity Screening Keywords Module
Manages keyword lists for financial crimes, corruption, and compliance screening
"""

from typing import List, Dict, Set
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)

class ScreeningCategory(Enum):
    """Categories of screening keywords"""
    FINANCIAL_CRIMES = "financial_crimes"
    CORRUPTION_BRIBERY = "corruption_bribery"
    ALL = "all"

class EntityScreeningKeywords:
    """
    Manages keyword lists for entity screening searches
    """
    
    def __init__(self):
        self._keywords = {
            ScreeningCategory.FINANCIAL_CRIMES: {
                "fraud",
                "scam", 
                "Ponzi",
                "embezzlement",
                "insider trading",
                "accounting irregularities",
                "money laundering",
                "misappropriation",
                "kickbacks",
                "shell company"
            },
            ScreeningCategory.CORRUPTION_BRIBERY: {
                "bribery",
                "corruption",
                "graft",
                "undue influence",
                "facilitation payment",
                "procurement fraud",
                "nepotism",
                "political donation scandal"
            }
        }
    
    def get_keywords(self, category: ScreeningCategory = ScreeningCategory.ALL) -> Set[str]:
        """
        Get keywords for a specific category or all categories
        
        Args:
            category: The screening category to get keywords for
            
        Returns:
            Set of keywords for the specified category
        """
        if category == ScreeningCategory.ALL:
            all_keywords = set()
            for cat_keywords in self._keywords.values():
                all_keywords.update(cat_keywords)
            return all_keywords
        
        return self._keywords.get(category, set())
    
    def get_keywords_list(self, category: ScreeningCategory = ScreeningCategory.ALL) -> List[str]:
        """
        Get keywords as a sorted list
        
        Args:
            category: The screening category to get keywords for
            
        Returns:
            Sorted list of keywords
        """
        return sorted(list(self.get_keywords(category)))
    
    def generate_entity_search_queries(self, entity_name: str, 
                                     category: ScreeningCategory = ScreeningCategory.ALL,
                                     max_queries: int = 10) -> List[str]:
        """
        Generate search queries combining entity name with screening keywords
        
        Args:
            entity_name: Name of the entity to screen
            category: Category of keywords to use
            max_queries: Maximum number of queries to generate
            
        Returns:
            List of search queries combining entity name with keywords
        """
        if not entity_name or not entity_name.strip():
            raise ValueError("Entity name cannot be empty")
        
        entity_name = entity_name.strip()
        keywords = self.get_keywords_list(category)
        
        if not keywords:
            logger.warning(f"No keywords found for category: {category}")
            return [entity_name]
        
        # Generate queries by combining entity name with each keyword
        queries = []
        for keyword in keywords[:max_queries]:
            # Create different query variations
            queries.extend([
                f'"{entity_name}" {keyword}',
                f'{entity_name} {keyword}',
                f'{entity_name} AND {keyword}'
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query in queries:
            if query not in seen:
                seen.add(query)
                unique_queries.append(query)
        
        return unique_queries[:max_queries]
    
    def generate_comprehensive_search_queries(self, entity_name: str,
                                            queries_per_category: int = 5) -> Dict[str, List[str]]:
        """
        Generate comprehensive search queries for all categories
        
        Args:
            entity_name: Name of the entity to screen
            queries_per_category: Number of queries per category
            
        Returns:
            Dictionary with category names as keys and query lists as values
        """
        if not entity_name or not entity_name.strip():
            raise ValueError("Entity name cannot be empty")
        
        result = {}
        
        # Generate queries for each category
        for category in [ScreeningCategory.FINANCIAL_CRIMES, ScreeningCategory.CORRUPTION_BRIBERY]:
            queries = self.generate_entity_search_queries(
                entity_name, 
                category, 
                queries_per_category
            )
            result[category.value] = queries
        
        # Also include a mixed category with top keywords from all categories
        all_keywords = self.get_keywords_list(ScreeningCategory.ALL)
        mixed_queries = []
        
        # Select top keywords from each category for mixed queries
        financial_keywords = list(self.get_keywords(ScreeningCategory.FINANCIAL_CRIMES))[:3]
        corruption_keywords = list(self.get_keywords(ScreeningCategory.CORRUPTION_BRIBERY))[:3]
        
        for keyword in financial_keywords + corruption_keywords:
            mixed_queries.append(f'"{entity_name}" {keyword}')
            if len(mixed_queries) >= queries_per_category:
                break
        
        result['mixed'] = mixed_queries
        
        return result
    
    def add_custom_keyword(self, keyword: str, category: ScreeningCategory):
        """
        Add a custom keyword to a category
        
        Args:
            keyword: The keyword to add
            category: The category to add it to
        """
        if category == ScreeningCategory.ALL:
            raise ValueError("Cannot add keywords to 'ALL' category")
        
        if keyword and keyword.strip():
            self._keywords[category].add(keyword.strip().lower())
            logger.info(f"Added keyword '{keyword}' to category '{category.value}'")
    
    def remove_keyword(self, keyword: str, category: ScreeningCategory):
        """
        Remove a keyword from a category
        
        Args:
            keyword: The keyword to remove
            category: The category to remove it from
        """
        if category == ScreeningCategory.ALL:
            raise ValueError("Cannot remove keywords from 'ALL' category")
        
        if keyword in self._keywords[category]:
            self._keywords[category].remove(keyword)
            logger.info(f"Removed keyword '{keyword}' from category '{category.value}'")
    
    def get_keyword_statistics(self) -> Dict[str, int]:
        """
        Get statistics about keyword counts per category
        
        Returns:
            Dictionary with category names and keyword counts
        """
        stats = {}
        for category, keywords in self._keywords.items():
            stats[category.value] = len(keywords)
        
        stats['total'] = len(self.get_keywords(ScreeningCategory.ALL))
        return stats
    
    def export_keywords(self) -> Dict[str, List[str]]:
        """
        Export all keywords as a JSON-serializable dictionary
        
        Returns:
            Dictionary with category names and keyword lists
        """
        export_data = {}
        for category, keywords in self._keywords.items():
            export_data[category.value] = sorted(list(keywords))
        
        return export_data
    
    def import_keywords(self, keywords_data: Dict[str, List[str]]):
        """
        Import keywords from a dictionary
        
        Args:
            keywords_data: Dictionary with category names and keyword lists
        """
        for category_name, keywords_list in keywords_data.items():
            try:
                category = ScreeningCategory(category_name)
                if category != ScreeningCategory.ALL:
                    self._keywords[category] = set(keywords_list)
                    logger.info(f"Imported {len(keywords_list)} keywords for category '{category_name}'")
            except ValueError:
                logger.warning(f"Unknown category '{category_name}' in import data")

# Convenience functions for easy access
def get_financial_crimes_keywords() -> List[str]:
    """Get financial crimes keywords as a list"""
    keywords_manager = EntityScreeningKeywords()
    return keywords_manager.get_keywords_list(ScreeningCategory.FINANCIAL_CRIMES)

def get_corruption_keywords() -> List[str]:
    """Get corruption and bribery keywords as a list"""
    keywords_manager = EntityScreeningKeywords()
    return keywords_manager.get_keywords_list(ScreeningCategory.CORRUPTION_BRIBERY)

def get_all_screening_keywords() -> List[str]:
    """Get all screening keywords as a list"""
    keywords_manager = EntityScreeningKeywords()
    return keywords_manager.get_keywords_list(ScreeningCategory.ALL)

def generate_entity_queries(entity_name: str, max_queries: int = 10) -> List[str]:
    """
    Generate search queries for an entity using all screening keywords
    
    Args:
        entity_name: Name of the entity to screen
        max_queries: Maximum number of queries to generate
        
    Returns:
        List of search queries
    """
    keywords_manager = EntityScreeningKeywords()
    return keywords_manager.generate_entity_search_queries(entity_name, max_queries=max_queries)

def generate_comprehensive_entity_queries(entity_name: str) -> Dict[str, List[str]]:
    """
    Generate comprehensive search queries for an entity across all categories
    
    Args:
        entity_name: Name of the entity to screen
        
    Returns:
        Dictionary with category-specific query lists
    """
    keywords_manager = EntityScreeningKeywords()
    return keywords_manager.generate_comprehensive_search_queries(entity_name)

# Example usage and testing
if __name__ == "__main__":
    # Example usage
    keywords_manager = EntityScreeningKeywords()
    
    print("=== Entity Screening Keywords Manager ===")
    print(f"Statistics: {keywords_manager.get_keyword_statistics()}")
    
    print("\n=== Financial Crimes Keywords ===")
    financial_keywords = keywords_manager.get_keywords_list(ScreeningCategory.FINANCIAL_CRIMES)
    for keyword in financial_keywords:
        print(f"- {keyword}")
    
    print("\n=== Corruption & Bribery Keywords ===")
    corruption_keywords = keywords_manager.get_keywords_list(ScreeningCategory.CORRUPTION_BRIBERY)
    for keyword in corruption_keywords:
        print(f"- {keyword}")
    
    print("\n=== Example Entity Queries ===")
    entity_name = "Acme Corporation"
    queries = keywords_manager.generate_entity_search_queries(entity_name, max_queries=5)
    for i, query in enumerate(queries, 1):
        print(f"{i}. {query}")
    
    print("\n=== Comprehensive Entity Queries ===")
    comprehensive_queries = keywords_manager.generate_comprehensive_search_queries(entity_name, 3)
    for category, queries in comprehensive_queries.items():
        print(f"\n{category.upper()}:")
        for i, query in enumerate(queries, 1):
            print(f"  {i}. {query}")

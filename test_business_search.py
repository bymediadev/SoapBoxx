#!/usr/bin/env python3
"""
Test script for business search functionality
"""

import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from guest_research import GuestResearch


def test_business_search():
    """Test the business search functionality"""
    print("🔍 Testing Business Search Functionality")
    print("=" * 50)

    # Initialize guest research
    gr = GuestResearch()

    # Test company search
    print("\n1. Testing Company Search...")
    company_results = gr.search_business("Microsoft", "company")
    print(
        f"✅ Company search completed: {len(company_results.get('results', []))} results"
    )

    # Test LinkedIn search
    print("\n2. Testing LinkedIn Search...")
    linkedin_results = gr.search_business("Microsoft", "linkedin")
    print(
        f"✅ LinkedIn search completed: {len(linkedin_results.get('linkedin_profiles', []))} profiles"
    )

    # Test executive search
    print("\n3. Testing Executive Search...")
    executive_results = gr.search_business("Microsoft", "executive")
    print(
        f"✅ Executive search completed: {len(executive_results.get('results', []))} results"
    )

    # Test news search
    print("\n4. Testing News Search...")
    news_results = gr.search_business("Microsoft", "news")
    print(f"✅ News search completed: {len(news_results.get('news', []))} articles")

    # Test comprehensive search
    print("\n5. Testing Comprehensive Search...")
    all_results = gr.search_business("Microsoft", "all")
    print(
        f"✅ Comprehensive search completed: {len(all_results.get('results', []))} total results"
    )

    if all_results.get("summary"):
        print(f"\n📋 Business Summary Preview:")
        summary = all_results["summary"]
        print(summary[:200] + "..." if len(summary) > 200 else summary)

    print("\n✅ All business search tests completed successfully!")


if __name__ == "__main__":
    test_business_search()

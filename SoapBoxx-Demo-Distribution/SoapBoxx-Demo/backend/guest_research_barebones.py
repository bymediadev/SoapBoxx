#!/usr/bin/env python3
"""
Barebones Guest Research for SoapBoxx Demo
Provides sample guest data without external web scraping dependencies
"""

import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class GuestProfile:
    """Guest profile information"""
    name: str
    title: str
    company: str
    bio: str
    expertise: List[str]
    social_media: Dict[str, str]
    recent_achievements: List[str]
    podcast_topics: List[str]
    contact_info: Dict[str, str]


class BarebonesGuestResearch:
    """Simplified guest research with sample data only"""
    
    def __init__(self):
        self.sample_guests = self._load_sample_guests()
        self.research_cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    def _load_sample_guests(self) -> Dict[str, GuestProfile]:
        """Load sample guest data"""
        return {
            "john_doe": GuestProfile(
                name="John Doe",
                title="CEO & Founder",
                company="TechStart Inc.",
                bio="Serial entrepreneur with 15+ years in software development. Founded 3 successful startups and helped scale 10+ companies.",
                expertise=["Software Development", "Startup Strategy", "Team Building", "Product Management"],
                social_media={
                    "linkedin": "linkedin.com/in/johndoe",
                    "twitter": "@johndoe",
                    "website": "johndoe.com"
                },
                recent_achievements=[
                    "Raised $50M Series B funding",
                    "Named to Forbes 30 Under 30",
                    "Company acquired for $200M"
                ],
                podcast_topics=[
                    "Building successful startups",
                    "Scaling engineering teams",
                    "Venture capital insights",
                    "Product-market fit"
                ],
                contact_info={
                    "email": "john@techstart.com",
                    "phone": "+1-555-0123"
                }
            ),
            "jane_smith": GuestProfile(
                name="Jane Smith",
                title="Chief Marketing Officer",
                company="GrowthCorp",
                bio="Marketing expert specializing in digital transformation and growth hacking. Led campaigns for Fortune 500 companies.",
                expertise=["Digital Marketing", "Growth Hacking", "Brand Strategy", "Customer Acquisition"],
                social_media={
                    "linkedin": "linkedin.com/in/janesmith",
                    "twitter": "@janesmith",
                    "instagram": "@janesmith_marketing"
                },
                recent_achievements=[
                    "Increased company revenue by 300%",
                    "Won Marketing Excellence Award",
                    "Featured in Harvard Business Review"
                ],
                podcast_topics=[
                    "Digital marketing strategies",
                    "Growth hacking techniques",
                    "Building brand awareness",
                    "Customer retention strategies"
                ],
                contact_info={
                    "email": "jane@growthcorp.com",
                    "phone": "+1-555-0456"
                }
            ),
            "mike_johnson": GuestProfile(
                name="Mike Johnson",
                title="Data Scientist",
                company="DataFlow Analytics",
                bio="Leading expert in machine learning and data science. PhD from MIT with 20+ research papers published.",
                expertise=["Machine Learning", "Data Science", "AI Ethics", "Statistical Analysis"],
                social_media={
                    "linkedin": "linkedin.com/in/mikejohnson",
                    "twitter": "@mikejohnson_ai",
                    "github": "github.com/mikejohnson"
                },
                recent_achievements=[
                    "Published in Nature Machine Intelligence",
                    "Led AI ethics committee",
                    "Developed breakthrough ML algorithm"
                ],
                podcast_topics=[
                    "Future of artificial intelligence",
                    "Machine learning applications",
                    "Data privacy and ethics",
                    "AI in business"
                ],
                contact_info={
                    "email": "mike@dataflow.com",
                    "phone": "+1-555-0789"
                }
            ),
            "sarah_wilson": GuestProfile(
                name="Sarah Wilson",
                title="Leadership Coach",
                company="LeadWell Consulting",
                bio="Executive coach and leadership development expert. Former Fortune 100 executive turned consultant.",
                expertise=["Leadership Development", "Executive Coaching", "Team Dynamics", "Change Management"],
                social_media={
                    "linkedin": "linkedin.com/in/sarahwilson",
                    "twitter": "@sarahwilson_lead",
                    "website": "leadwellconsulting.com"
                },
                recent_achievements=[
                    "Coached 50+ C-level executives",
                    "Published leadership book",
                    "Featured TEDx speaker"
                ],
                podcast_topics=[
                    "Building effective teams",
                    "Leadership in crisis",
                    "Executive communication",
                    "Workplace culture"
                ],
                contact_info={
                    "email": "sarah@leadwell.com",
                    "phone": "+1-555-0321"
                }
            ),
            "david_chen": GuestProfile(
                name="David Chen",
                title="Venture Capitalist",
                company="Innovate Capital",
                bio="Early-stage investor with focus on fintech and healthtech. Former founder with successful exit.",
                expertise=["Venture Capital", "Fintech", "Healthtech", "Investment Strategy"],
                social_media={
                    "linkedin": "linkedin.com/in/davidchen",
                    "twitter": "@davidchen_vc",
                    "website": "innovatecapital.com"
                },
                recent_achievements=[
                    "Invested in 5 unicorn companies",
                    "Named Top 100 VCs by Forbes",
                    "Exited company for $150M"
                ],
                podcast_topics=[
                    "Venture capital insights",
                    "Fintech trends",
                    "Healthtech innovation",
                    "Investment strategies"
                ],
                contact_info={
                    "email": "david@innovatecapital.com",
                    "phone": "+1-555-0654"
                }
            )
        }
    
    def research_guest(self, guest_name: str, company: str = None) -> Dict:
        """
        Research a guest using sample data
        """
        if not guest_name:
            return {"error": "Guest name is required"}
        
        # Check cache first
        cache_key = f"{guest_name.lower()}_{company.lower() if company else 'none'}"
        if cache_key in self.research_cache:
            cached = self.research_cache[cache_key]
            if time.time() - cached.get("timestamp", 0) < self.cache_ttl:
                return cached["result"]
        
        try:
            # Search sample data
            guest_profile = self._find_guest(guest_name, company)
            
            if guest_profile:
                result = self._format_guest_profile(guest_profile)
            else:
                result = self._create_mock_profile(guest_name, company)
            
            # Add metadata
            result["research_type"] = "sample_data"
            result["timestamp"] = time.time()
            result["data_source"] = "SoapBoxx Demo Sample Data"
            
            # Cache the result
            self.research_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            return {"error": f"Research failed: {str(e)}"}
    
    def _find_guest(self, guest_name: str, company: str = None) -> Optional[GuestProfile]:
        """Find guest in sample data"""
        guest_name_lower = guest_name.lower()
        
        # Exact match first
        for key, profile in self.sample_guests.items():
            if guest_name_lower in profile.name.lower():
                if company is None or company.lower() in profile.company.lower():
                    return profile
        
        # Partial match
        for key, profile in self.sample_guests.items():
            if any(word in profile.name.lower() for word in guest_name_lower.split()):
                if company is None or company.lower() in profile.company.lower():
                    return profile
        
        return None
    
    def _create_mock_profile(self, guest_name: str, company: str = None) -> Dict:
        """Create a mock profile for unknown guests"""
        company_name = company or "Unknown Company"
        
        return {
            "success": True,
            "guest_info": {
                "name": guest_name,
                "title": "Industry Professional",
                "company": company_name,
                "bio": f"{guest_name} is a professional in their field with expertise in their industry.",
                "expertise": ["Industry Knowledge", "Professional Experience", "Leadership"],
                "social_media": {
                    "linkedin": f"linkedin.com/in/{guest_name.lower().replace(' ', '')}",
                    "website": f"{guest_name.lower().replace(' ', '')}.com"
                },
                "recent_achievements": [
                    "Industry recognition",
                    "Professional accomplishments",
                    "Leadership roles"
                ],
                "podcast_topics": [
                    "Industry insights",
                    "Professional development",
                    "Leadership lessons",
                    "Industry trends"
                ],
                "contact_info": {
                    "email": f"{guest_name.lower().replace(' ', '.')}@{company_name.lower().replace(' ', '')}.com"
                }
            },
            "research_quality": "estimated",
            "confidence_score": 0.6
        }
    
    def _format_guest_profile(self, profile: GuestProfile) -> Dict:
        """Format guest profile for output"""
        return {
            "success": True,
            "guest_info": {
                "name": profile.name,
                "title": profile.title,
                "company": profile.company,
                "bio": profile.bio,
                "expertise": profile.expertise,
                "social_media": profile.social_media,
                "recent_achievements": profile.recent_achievements,
                "podcast_topics": profile.podcast_topics,
                "contact_info": profile.contact_info
            },
            "research_quality": "verified",
            "confidence_score": 0.95
        }
    
    def search_company_info(self, company_name: str) -> Dict:
        """Search for company information using sample data"""
        if not company_name:
            return {"error": "Company name is required"}
        
        # Check cache
        cache_key = f"company_{company_name.lower()}"
        if cache_key in self.research_cache:
            cached = self.research_cache[cache_key]
            if time.time() - cached.get("timestamp", 0) < self.cache_ttl:
                return cached["result"]
        
        try:
            # Find company in sample data
            company_info = self._find_company_info(company_name)
            
            if company_info:
                result = company_info
            else:
                result = self._create_mock_company_info(company_name)
            
            # Add metadata
            result["research_type"] = "sample_data"
            result["timestamp"] = time.time()
            result["data_source"] = "SoapBoxx Demo Sample Data"
            
            # Cache the result
            self.research_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            return {"error": f"Company research failed: {str(e)}"}
    
    def _find_company_info(self, company_name: str) -> Optional[Dict]:
        """Find company information in sample data"""
        company_name_lower = company_name.lower()
        
        # Sample company data
        sample_companies = {
            "techstart": {
                "name": "TechStart Inc.",
                "industry": "Software Development",
                "founded": "2015",
                "employees": "150",
                "funding": "$75M",
                "description": "Leading software development company specializing in enterprise solutions.",
                "key_products": ["Cloud Platform", "API Suite", "Analytics Dashboard"],
                "leadership": ["John Doe - CEO", "Lisa Wang - CTO", "Mark Johnson - CFO"]
            },
            "growthcorp": {
                "name": "GrowthCorp",
                "industry": "Marketing & Growth",
                "founded": "2018",
                "employees": "75",
                "funding": "$25M",
                "description": "Digital marketing agency focused on growth hacking and customer acquisition.",
                "key_products": ["Growth Platform", "Marketing Automation", "Analytics Tools"],
                "leadership": ["Jane Smith - CMO", "Tom Brown - CEO", "Amy Davis - COO"]
            },
            "dataflow": {
                "name": "DataFlow Analytics",
                "industry": "Data Science & AI",
                "founded": "2016",
                "employees": "120",
                "funding": "$45M",
                "description": "Advanced analytics and machine learning solutions for enterprise clients.",
                "key_products": ["ML Platform", "Data Pipeline", "AI Models"],
                "leadership": ["Mike Johnson - Chief Data Scientist", "Rachel Green - CEO", "Kevin Lee - CTO"]
            }
        }
        
        # Search for company
        for key, company in sample_companies.items():
            if key in company_name_lower or company_name_lower in company["name"].lower():
                return company
        
        return None
    
    def _create_mock_company_info(self, company_name: str) -> Dict:
        """Create mock company information"""
        return {
            "success": True,
            "company_info": {
                "name": company_name,
                "industry": "Technology",
                "founded": "2020",
                "employees": "50-100",
                "funding": "Undisclosed",
                "description": f"{company_name} is a technology company focused on innovation and growth.",
                "key_products": ["Software Solutions", "Digital Services", "Technology Consulting"],
                "leadership": ["Executive Team", "Management Team", "Advisory Board"]
            },
            "research_quality": "estimated",
            "confidence_score": 0.5
        }
    
    def get_industry_insights(self, industry: str) -> Dict:
        """Get industry insights using sample data"""
        if not industry:
            return {"error": "Industry is required"}
        
        # Sample industry insights
        industry_insights = {
            "technology": {
                "trends": ["AI/ML adoption", "Cloud migration", "Cybersecurity focus"],
                "growth_rate": "15% annually",
                "key_challenges": ["Talent shortage", "Rapid innovation", "Security threats"],
                "opportunities": ["Digital transformation", "Remote work solutions", "AI applications"]
            },
            "marketing": {
                "trends": ["Personalization", "Video content", "Social commerce"],
                "growth_rate": "12% annually",
                "key_challenges": ["Data privacy", "Ad fatigue", "ROI measurement"],
                "opportunities": ["Digital marketing", "Content creation", "Customer experience"]
            },
            "finance": {
                "trends": ["Fintech innovation", "Digital banking", "Cryptocurrency"],
                "growth_rate": "8% annually",
                "key_challenges": ["Regulation", "Cybersecurity", "Digital transformation"],
                "opportunities": ["Financial technology", "Digital services", "Investment platforms"]
            }
        }
        
        industry_lower = industry.lower()
        
        # Find matching industry
        for key, insights in industry_insights.items():
            if key in industry_lower or industry_lower in key:
                return {
                    "success": True,
                    "industry": industry,
                    "insights": insights,
                    "data_source": "Sample Industry Data"
                }
        
        # Return generic insights
        return {
            "success": True,
            "industry": industry,
            "insights": {
                "trends": ["Digital transformation", "Innovation", "Growth"],
                "growth_rate": "10% annually",
                "key_challenges": ["Competition", "Technology adoption", "Market changes"],
                "opportunities": ["Innovation", "Digital services", "Market expansion"]
            },
            "data_source": "Generic Industry Data"
        }
    
    def clear_cache(self):
        """Clear the research cache"""
        self.research_cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.research_cache),
            "cache_ttl": self.cache_ttl,
            "total_guests": len(self.sample_guests),
            "cache_hits": 0  # Simplified - no hit tracking in barebones version
        }

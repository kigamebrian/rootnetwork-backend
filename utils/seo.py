# utils/seo.py
import re

class SEOHelper:
    """Helper class for SEO improvements"""
    
    @staticmethod
    def generate_meta_description(content, max_length=160):
        """Generate meta description from content"""
        if not content:
            return "Read our latest blog post for insights and updates."
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', content)
        # Remove extra whitespace
        clean_text = ' '.join(clean_text.split())
        # Truncate to max length
        if len(clean_text) > max_length:
            clean_text = clean_text[:max_length-3] + '...'
        return clean_text if clean_text else "Read our latest blog post."
    
    @staticmethod
    def generate_keywords(title, category=None):
        """Generate keywords from title and category"""
        keywords = set()
        
        # Add words from title
        for word in title.lower().split():
            # Only include words longer than 3 characters
            if len(word) > 3:
                keywords.add(word)
        
        # Add category
        if category:
            keywords.add(category.lower())
        
        # Add common blog keywords
        common_keywords = ['blog', 'article', 'news', 'update', 'guide', 'tips', 'information']
        keywords.update(common_keywords)
        
        return ', '.join(list(keywords)[:10])
    
    @staticmethod
    def calculate_read_time(content):
        """Calculate estimated reading time in minutes"""
        if not content:
            return 1
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', content)
        # Count words
        word_count = len(clean_text.split())
        # Average reading speed: 200-250 words per minute
        minutes = max(1, round(word_count / 200))
        return minutes

seo_helper = SEOHelper()
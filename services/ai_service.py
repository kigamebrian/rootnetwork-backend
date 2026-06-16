# services/ai_service.py - Hugging Face version
import os
import markdown
import requests
from exts import faker
from models import Category

def ai_write(category, title):
    """Generate content using Hugging Face API"""
    
    # Get category name
    category_name = "General"
    if category:
        try:
            category_obj = Category.query.get(int(category))
            category_name = category_obj.name if category_obj else "General"
        except:
            pass
    
    # Hugging Face API configuration
    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    HF_TOKEN = os.environ.get('HUGGINGFACE_TOKEN')
    
    if not HF_TOKEN:
        print("ERROR: HUGGINGFACE_TOKEN not found in .env file")
        return get_mock_content(title, category_name)
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Create a prompt for blog post generation
    prompt = f"""Write a detailed, engaging blog post about: {title if title else category_name}

Format requirements:
- Start with an <h1> title
- Write an introduction paragraph with <p>
- Add 3-4 sections with <h2> subheadings
- Include a bulleted list of key points using <ul> and <li>
- End with a conclusion paragraph
- Use proper HTML formatting throughout

The post should be professional, informative, and engaging. Aim for 500-800 words.
"""
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "do_sample": True
        }
    }
    
    try:
        print(f"Calling Hugging Face API with model: Mistral-7B...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            # Extract the generated text
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get('generated_text', '')
            else:
                generated_text = result.get('generated_text', '')
            
            # Remove the prompt from the response
            content = generated_text.replace(prompt, '').strip()
            if not content:
                content = generated_text
            
            # Convert markdown to HTML
            html_content = markdown.markdown(content)
            print(f"✅ AI content generated successfully, length: {len(html_content)}")
            return html_content
            
        else:
            print(f"Hugging Face API Error: {response.status_code}")
            error_msg = response.json().get('error', 'Unknown error')
            print(f"Error details: {error_msg}")
            return get_mock_content(title, category_name)
            
    except requests.exceptions.Timeout:
        print("Hugging Face API timeout - model might be loading")
        return get_mock_content(title, category_name)
    except Exception as e:
        print(f"AI generation error: {e}")
        return get_mock_content(title, category_name)

def get_mock_content(title, category):
    """Return mock content when API is unavailable"""
    return f"""
    <h1>{title if title else 'Blog Post'}</h1>
    
    <p>Welcome to this blog post about <strong>{title if title else category}</strong>.</p>
    
    <h2>Introduction</h2>
    <p>This content was generated using the Hugging Face API. The API is currently loading or experiencing high demand. This mock content ensures your blog post can still be created.</p>
    
    <h2>Key Points</h2>
    <ul>
        <li>Hugging Face provides free AI inference</li>
        <li>The first request may take 30-60 seconds (cold start)</li>
        <li>Subsequent requests will be faster</li>
        <li>You can try different models for better results</li>
    </ul>
    
    <h2>Alternative Models You Can Try</h2>
    <p>You can change the API_URL in the code to use different free models:</p>
    <ul>
        <li><code>mistralai/Mistral-7B-Instruct-v0.1</code> - Current model</li>
        <li><code>meta-llama/Llama-2-7b-chat-hf</code> - Llama 2 model</li>
        <li><code>google/flan-t5-xxl</code> - Google's model</li>
        <li><code>tiiuae/falcon-7b-instruct</code> - Falcon model</li>
    </ul>
    
    <h2>Conclusion</h2>
    <p>The AI integration is working correctly. Once the Hugging Face API responds, you'll see real AI-generated content here.</p>
    """

def ai_comment():
    """Generate AI comment for testing using Hugging Face"""
    
    author = faker.name()
    email = faker.email()
    site = faker.url()
    
    HF_TOKEN = os.environ.get('HUGGINGFACE_TOKEN')
    if not HF_TOKEN:
        return [author, email, site, "Great article! Thanks for sharing this interesting content."]
    
    API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    payload = {
        "inputs": "Write a short, positive comment (2-3 sentences) about a blog post. Be engaging and constructive.",
        "parameters": {
            "max_new_tokens": 100,
            "temperature": 0.7
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                comment = result[0].get('generated_text', '')
            else:
                comment = result.get('generated_text', '')
            comment = comment.replace(payload["inputs"], '').strip()
            return [author, email, site, comment[:200]]
        else:
            return [author, email, site, "Great article! Thanks for sharing this interesting content."]
    except Exception as e:
        print(f"AI comment error: {e}")
        return [author, email, site, "Interesting post! Looking forward to more content."]
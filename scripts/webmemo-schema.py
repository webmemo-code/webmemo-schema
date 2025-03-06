# webmemo-schema.py
# Schema.org data collection and management for Webmemo.ch

import requests
import json
import pandas as pd
import argparse
import os
import time
from datetime import datetime
from google.colab import auth, drive
import gspread
from oauth2client.client import GoogleCredentials
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Check if running in Google Colab
IN_COLAB = 'google.colab' in str(get_ipython())

# Conditional imports based on environment
if IN_COLAB:
    from google.colab import auth as colab_auth, drive
    import gspread
    from oauth2client.client import GoogleCredentials
else:
    # For non-Colab environments like GitHub Actions
    import gspread
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

# Get credentials from environment variables
WP_API_USER = os.getenv('WP_API_TESTER')
WP_API_PASSWORD = os.getenv('WP_API_PW')

# Configuration
WP_API_BASE = 'https://webmemo.ch/wp-json/wp/v2'
SCHEMA_API_BASE = 'https://webmemo.ch/wp-json/webmemo-schema/v1'
ENDPOINTS = {
    'posts': f'{WP_API_BASE}/posts',
    'pages': f'{WP_API_BASE}/pages',
    'categories': f'{WP_API_BASE}/categories',
    'tags': f'{WP_API_BASE}/tags',
    'users': f'{WP_API_BASE}/users',
    'media': f'{WP_API_BASE}/media',
    'schema': f'{SCHEMA_API_BASE}/schemas'
}

def authenticate():
    """Authenticate with Google services based on environment"""
    print("Authenticating with Google...")
    
    if IN_COLAB:
        # Colab-specific authentication
        colab_auth.authenticate_user()
        drive.mount('/content/drive')
        return gspread.authorize(GoogleCredentials.get_application_default())
    else:
        # Standard service account authentication
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        return gspread.authorize(credentials)

def fetch_all_pages(endpoint, params=None):
    """Fetch all pages from a paginated WordPress REST API endpoint"""
    if params is None:
        params = {}
    
    # Default to 100 items per page
    params.setdefault('per_page', 100)
    params.setdefault('page', 1)
    
    all_items = []
    
    print(f"Fetching data from {endpoint}...")
    
    while True:
        response = requests.get(endpoint, params=params)
        
        # Break if we get an error
        if response.status_code != 200:
            print(f"Error fetching data from {endpoint}: {response.status_code}")
            break
        
        # Get the items from the current page
        items = response.json()
        
        # If no items were returned, break
        if not items:
            break
        
        # Add the items to our list
        all_items.extend(items)
        
        # Move to the next page
        params['page'] += 1
    
    print(f"Retrieved {len(all_items)} items from {endpoint}")
    return all_items

def fetch_data():
    """Fetch all necessary data from WordPress"""
    data = {}
    
    # Fetch posts with metadata (author, categories, tags, featured image)
    data['posts'] = fetch_all_pages(ENDPOINTS['posts'], {
        '_embed': True,  # Include embedded data like author, featured image
        'status': 'publish'  # Only published posts
    })
    
    # Fetch pages
    data['pages'] = fetch_all_pages(ENDPOINTS['pages'], {
        '_embed': True,
        'status': 'publish'
    })
    
    # Fetch authors/users
    data['users'] = fetch_all_pages(ENDPOINTS['users'])
    
    # Fetch categories
    data['categories'] = fetch_all_pages(ENDPOINTS['categories'])
    
    # Fetch tags
    data['tags'] = fetch_all_pages(ENDPOINTS['tags'])
    
    return data

def generate_person_schema(user_data):
    """Generate Schema.org Person markup for a WordPress user"""
    user_slug = user_data['slug']
    user_url = f"https://api.webmemo.ch/author/{user_slug}"
    
    schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "@id": user_url,
        "name": user_data['name'],
        "url": user_url,
        "description": user_data.get('description', '')
    }
    
    # Add optional properties if available
    if 'user_email' in user_data:
        schema['email'] = user_data['user_email']
    
    # Add social media profiles if available (would need to come from user meta)
    # This would need to be expanded with actual data from your site
    social_profiles = []
    if social_profiles:
        schema['sameAs'] = social_profiles
    
    return schema

def generate_article_schema(post_data):
    """Generate Schema.org Article markup for a WordPress post"""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post_data['title']['rendered'],
        "datePublished": post_data['date'],
        "dateModified": post_data['modified'],
        "url": post_data['link'],
        "author": {
            "@type": "Person",
            "@id": f"https://webmemo.ch/author/{post_data['_embedded']['author'][0]['slug']}"
        },
        "publisher": {
            "@id": "https://webmemo.ch/#consulting"
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": post_data['link']
        }
    }
    
    # Add featured image if available
    if 'featured_media' in post_data and post_data['featured_media'] > 0:
        if 'wp:featuredmedia' in post_data['_embedded'] and post_data['_embedded']['wp:featuredmedia']:
            media = post_data['_embedded']['wp:featuredmedia'][0]
            if 'source_url' in media:
                schema["image"] = {
                    "@type": "ImageObject",
                    "url": media['source_url'],
                    "width": media.get('width', 1200),
                    "height": media.get('height', 630)
                }
    
    # Add categories and tags as keywords
    if 'wp:term' in post_data['_embedded']:
        terms = post_data['_embedded']['wp:term']
        keywords = []
        
        # Categories (usually in the first term array)
        if len(terms) > 0:
            keywords.extend([term['name'] for term in terms[0]])
        
        # Tags (usually in the second term array)
        if len(terms) > 1:
            keywords.extend([term['name'] for term in terms[1]])
        
        if keywords:
            schema["keywords"] = ", ".join(keywords)
    
    return schema

def save_to_sheet(gc, data, sheet_name):
    """Save data to a Google Sheet"""
    try:
        # Convert data to DataFrame
        df = pd.json_normalize(data)
        
        # Create or open the sheet
        try:
            sheet = gc.open(sheet_name)
        except:
            sheet = gc.create(sheet_name)
        
        # Get or create worksheet
        try:
            worksheet = sheet.get_worksheet(0)
        except:
            worksheet = sheet.add_worksheet(title="Data", rows=1, cols=1)
        
        # Clear worksheet
        worksheet.clear()
        
        # Update with data
        worksheet.update([df.columns.tolist()] + df.values.tolist())
        
        print(f"Saved {len(data)} items to Google Sheet: {sheet_name}")
        
        return sheet.url
    except Exception as e:
        print(f"Error saving to sheet: {e}")
        return None

def generate_schemas(data):
    """Generate Schema.org JSON-LD for all entities"""
    schemas = []
    
    # Generate Person schemas for users
    for user in data['users']:
        schema = generate_person_schema(user)
        schemas.append({
            'object_id': user['id'],
            'object_type': 'user',
            'schema_type': 'Person',
            'schema_data': json.dumps(schema),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Generate Article schemas for posts
    for post in data['posts']:
        schema = generate_article_schema(post)
        schemas.append({
            'object_id': post['id'],
            'object_type': 'post',
            'schema_type': 'Article',
            'schema_data': json.dumps(schema),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Add more schema generators as needed (WebPage, Product, etc.)
    
    return schemas

def upload_schemas(schemas, batch_size=50):
    """Upload schemas to WordPress via REST API"""
    # This would require authentication and API access
    # You would need to implement WordPress authentication
    
    # Example code - not functional without proper auth
    total_success = 0
    total_errors = 0
    
    # Split into batches
    for i in range(0, len(schemas), batch_size):
        batch = schemas[i:i+batch_size]
        
        try:
            # This is a placeholder for the actual API request
            # You would need to implement authentication
            response = requests.post(
                ENDPOINTS['schema'],
                json={'schemas': batch},
                # Add authentication here
            )
            
            if response.status_code == 200:
                result = response.json()
                batch_success = len(result.get('success', []))
                batch_errors = len(result.get('errors', []))
                
                total_success += batch_success
                total_errors += batch_errors
                
                print(f"Batch {i//batch_size + 1}: Uploaded {batch_success} schemas, {batch_errors} errors")
            else:
                print(f"Batch {i//batch_size + 1}: Failed with status {response.status_code}")
                total_errors += len(batch)
            
        except Exception as e:
            print(f"Error uploading batch {i//batch_size + 1}: {e}")
            total_errors += len(batch)
        
        # Sleep to avoid overwhelming the server
        time.sleep(1)
    
    print(f"Schema upload complete! Success: {total_success}, Errors: {total_errors}")
    return total_success, total_errors

def validate_schemas(urls):
    """Validate Schema.org implementations on given URLs"""
    results = []
    
    for url in urls:
        print(f"Validating {url}...")
        
        try:
            # Fetch the page
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"Error fetching {url}: {response.status_code}")
                continue
            
            # Use regex to extract JSON-LD scripts (more reliable than BeautifulSoup for JSON-LD)
            pattern = r'<script type="application/ld\+json">(.*?)</script>'
            matches = re.findall(pattern, response.text, re.DOTALL)
            
            if not matches:
                print(f"No Schema.org JSON-LD found on {url}")
                continue
            
            # Parse and validate each script
            for i, script_content in enumerate(matches):
                try:
                    # Parse the JSON
                    schema_data = json.loads(script_content)
                    
                    # Extract the Schema type
                    schema_type = schema_data.get('@type', 'Unknown')
                    
                    # Add to results
                    results.append({
                        'url': url,
                        'schema_index': i,
                        'schema_type': schema_type,
                        'valid_json': True,
                        'schema_data': json.dumps(schema_data)
                    })
                    
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON in schema #{i} on {url}: {e}")
                    results.append({
                        'url': url,
                        'schema_index': i,
                        'schema_type': 'Invalid JSON',
                        'valid_json': False,
                        'error': str(e),
                        'schema_data': script_content
                    })
        
        except Exception as e:
            print(f"Error validating {url}: {e}")
        
        # Sleep to avoid too many requests
        time.sleep(1)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Schema.org data collection and management for Webmemo.ch')
    parser.add_argument('--fetch', action='store_true', help='Fetch data from WordPress')
    parser.add_argument('--generate', action='store_true', help='Generate Schema.org data')
    parser.add_argument('--upload', action='store_true', help='Upload Schema.org data to WordPress')
    parser.add_argument('--validate', action='store_true', help='Validate Schema.org implementations')
    parser.add_argument('--all', action='store_true', help='Run all steps')
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    # Authenticate with Google
    gc = authenticate()
    
    # Process based on arguments
    if args.all or args.fetch:
        print("=== Fetching data from WordPress ===")
        data = fetch_data()
        
        # Save data to Google Sheets
        for entity_type, entity_data in data.items():
            save_to_sheet(gc, entity_data, f"Webmemo {entity_type.capitalize()}")
    
    if args.all or args.generate:
        print("=== Generating Schema.org data ===")
        # Either load data from sheets or fetch again
        data = fetch_data()  # For simplicity, we're fetching again
        
        schemas = generate_schemas(data)
        
        # Save schemas to Google Sheet
        save_to_sheet(gc, schemas, "Webmemo Schemas")
    
    if args.all or args.upload:
        print("=== Uploading Schema.org data to WordPress ===")
        # Load schemas from Google Sheet
        # This is placeholder code - you would need to implement sheet loading
        schemas = []  # Replace with actual data loading
        
        upload_schemas(schemas)
    
    if args.all or args.validate:
        print("=== Validating Schema.org implementations ===")
        urls = [
            'https://webmemo.ch',
            'https://webmemo.ch/kontakt-ueber-mich-walter-schaerer',
            # Add more URLs as needed
        ]
        
        results = validate_schemas(urls)
        
        # Save validation results
        save_to_sheet(gc, results, "Webmemo Schema Validation")

if __name__ == "__main__":
    main()
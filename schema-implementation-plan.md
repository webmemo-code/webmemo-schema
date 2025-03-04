# Webmemo Schema.org Implementation Plan
# For api.webmemo.ch test server

## 1. Plugin Structure

Create a custom WordPress plugin called `webmemo-schema`:

```
webmemo-schema/
├── webmemo-schema.php          # Main plugin file
├── includes/
│   ├── class-schema-manager.php          # Core Schema management
│   ├── class-schema-types.php            # Schema type definitions
│   ├── class-schema-admin.php            # Admin interface
│   ├── class-schema-rest-api.php         # REST API endpoints
│   └── class-schema-db.php               # Database interactions
├── admin/
│   ├── js/
│   └── css/
└── README.md
```

## 2. Database Structure

Create a custom table to store the Schema data:

```sql
CREATE TABLE {wp_prefix}_webmemo_schema (
    schema_id BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
    object_id BIGINT(20) UNSIGNED NOT NULL,
    object_type VARCHAR(20) NOT NULL,
    schema_type VARCHAR(50) NOT NULL,
    schema_data LONGTEXT NOT NULL,
    last_updated DATETIME NOT NULL,
    PRIMARY KEY (schema_id),
    KEY object_id (object_id),
    KEY object_type (object_type),
    KEY schema_type (schema_type)
) {$charset_collate};
```

## 3. Python Script for Data Collection

Create a Python script to extract data from WordPress:

```python
import requests
import json
import pandas as pd
from google.colab import auth
import gspread
from oauth2client.client import GoogleCredentials

# Authenticate and create a client
auth.authenticate_user()
gc = gspread.authorize(GoogleCredentials.get_application_default())

# WordPress REST API endpoints
WP_API_BASE = 'https://api.webmemo.ch/wp-json/wp/v2'
ENDPOINTS = {
    'posts': f'{WP_API_BASE}/posts',
    'pages': f'{WP_API_BASE}/pages',
    'categories': f'{WP_API_BASE}/categories',
    'tags': f'{WP_API_BASE}/tags',
    'users': f'{WP_API_BASE}/users',
    'media': f'{WP_API_BASE}/media'
}

def fetch_all_pages(endpoint, params=None):
    """Fetch all pages from a paginated WordPress REST API endpoint"""
    if params is None:
        params = {}
    
    # Start with page 1 and get 100 items per page
    params['page'] = 1
    params['per_page'] = 100
    
    all_items = []
    
    while True:
        response = requests.get(endpoint, params=params)
        
        # Break if we get an error (like 400 for requesting a page that doesn't exist)
        if response.status_code != 200:
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
    
    return all_items

# Example: Fetch all posts
posts = fetch_all_pages(ENDPOINTS['posts'])

# Convert to DataFrame for easier manipulation
posts_df = pd.json_normalize(posts)

# Save to Google Sheets for review/editing
sheet = gc.create('Webmemo Posts Data')
worksheet = sheet.get_worksheet(0)
worksheet.update([posts_df.columns.tolist()] + posts_df.values.tolist())

print(f"Saved {len(posts)} posts to Google Sheet: {sheet.url}")
```

## 4. Schema Generation Script

Create a script to generate Schema.org JSON-LD from the collected data:

```python
import json
import pandas as pd
from datetime import datetime

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
            "@id": f"https://webmemo.ch/author/{post_data['author_info']['slug']}"
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
        schema["image"] = {
            "@type": "ImageObject",
            "url": post_data['_embedded']['wp:featuredmedia'][0]['source_url'],
            "width": post_data['_embedded']['wp:featuredmedia'][0]['width'],
            "height": post_data['_embedded']['wp:featuredmedia'][0]['height']
        }
    
    # Add categories as keywords
    if '_embedded' in post_data and 'wp:term' in post_data['_embedded']:
        categories = [term['name'] for term in post_data['_embedded']['wp:term'][0]]
        tags = [term['name'] for term in post_data['_embedded']['wp:term'][1]]
        schema["keywords"] = ", ".join(categories + tags)
    
    return schema

# Load the posts data from Google Sheets or another source
# posts_df = ...

# Generate schema for each post
schemas = []
for _, post in posts_df.iterrows():
    post_dict = post.to_dict()
    schema = generate_article_schema(post_dict)
    schemas.append({
        'object_id': post_dict['id'],
        'object_type': 'post',
        'schema_type': 'Article',
        'schema_data': json.dumps(schema),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# Convert to DataFrame
schemas_df = pd.DataFrame(schemas)

# Save to Google Sheets or directly to WordPress database
# ...
```

## 5. WordPress Plugin Core Implementation

The main plugin file (`webmemo-schema.php`):

```php
<?php
/**
 * Plugin Name: Webmemo Schema.org
 * Description: Advanced Schema.org implementation for Webmemo.ch
 * Version: 1.0.0
 * Author: Walter Schärer
 * Author URI: https://webmemo.ch/author/walter-schaerer
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

// Define plugin constants
define('WEBMEMO_SCHEMA_VERSION', '1.0.0');
define('WEBMEMO_SCHEMA_PATH', plugin_dir_path(__FILE__));
define('WEBMEMO_SCHEMA_URL', plugin_dir_url(__FILE__));

// Include required files
require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-db.php';
require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-types.php';
require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-manager.php';
require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-rest-api.php';
require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-admin.php';

// Activation hook
register_activation_hook(__FILE__, 'webmemo_schema_activate');
function webmemo_schema_activate() {
    // Create database tables
    $schema_db = new Webmemo_Schema_DB();
    $schema_db->create_tables();
}

// Deactivation hook
register_deactivation_hook(__FILE__, 'webmemo_schema_deactivate');
function webmemo_schema_deactivate() {
    // Clean up if needed
}

// Initialize the plugin
function webmemo_schema_init() {
    // Initialize the Schema Manager
    $schema_manager = new Webmemo_Schema_Manager();
    
    // Initialize admin interface
    if (is_admin()) {
        $schema_admin = new Webmemo_Schema_Admin();
    }
    
    // Initialize REST API endpoints
    $schema_rest_api = new Webmemo_Schema_REST_API();
}
add_action('plugins_loaded', 'webmemo_schema_init');

// Add Schema.org markup to head
function webmemo_schema_add_to_head() {
    $schema_manager = new Webmemo_Schema_Manager();
    $schema_data = $schema_manager->get_schema_for_current_page();
    
    if (!empty($schema_data)) {
        foreach ($schema_data as $schema) {
            echo '<script type="application/ld+json">' . $schema . '</script>' . "\n";
        }
    }
}
add_action('wp_head', 'webmemo_schema_add_to_head', 99);
```

## 6. Schema Manager Class

The Schema Manager class (`class-schema-manager.php`):

```php
<?php
/**
 * Schema Manager Class
 */
class Webmemo_Schema_Manager {
    
    private $db;
    private $types;
    
    public function __construct() {
        $this->db = new Webmemo_Schema_DB();
        $this->types = new Webmemo_Schema_Types();
    }
    
    /**
     * Get Schema data for the current page
     */
    public function get_schema_for_current_page() {
        global $post;
        $schemas = array();
        
        // Add global schemas
        $global_schemas = $this->get_global_schemas();
        $schemas = array_merge($schemas, $global_schemas);
        
        // If singular post/page, add its schema
        if (is_singular() && isset($post)) {
            $post_schemas = $this->get_schemas_for_object($post->ID, 'post');
            $schemas = array_merge($schemas, $post_schemas);
        }
        
        // If author page, add author schema
        if (is_author()) {
            $author_id = get_the_author_meta('ID');
            $author_schemas = $this->get_schemas_for_object($author_id, 'user');
            $schemas = array_merge($schemas, $author_schemas);
        }
        
        return $schemas;
    }
    
    /**
     * Get global schemas (WebSite, Organization, etc.)
     */
    public function get_global_schemas() {
        return $this->db->get_schemas_by_type('global');
    }
    
    /**
     * Get schemas for a specific object
     */
    public function get_schemas_for_object($object_id, $object_type) {
        return $this->db->get_schemas_by_object($object_id, $object_type);
    }
    
    /**
     * Save schema data for an object
     */
    public function save_schema($object_id, $object_type, $schema_type, $schema_data) {
        return $this->db->save_schema($object_id, $object_type, $schema_type, $schema_data);
    }
    
    /**
     * Delete schema data for an object
     */
    public function delete_schema($schema_id) {
        return $this->db->delete_schema($schema_id);
    }
}
```

## 7. REST API Endpoints

Create REST API endpoints for the Python scripts to interact with (`class-schema-rest-api.php`):

```php
<?php
/**
 * Schema REST API Class
 */
class Webmemo_Schema_REST_API {
    
    private $namespace = 'webmemo-schema/v1';
    private $schema_manager;
    
    public function __construct() {
        $this->schema_manager = new Webmemo_Schema_Manager();
        add_action('rest_api_init', array($this, 'register_routes'));
    }
    
    /**
     * Register REST API routes
     */
    public function register_routes() {
        // Get schemas
        register_rest_route($this->namespace, '/schemas', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_schemas'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
        
        // Get schema by ID
        register_rest_route($this->namespace, '/schemas/(?P<id>\d+)', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_schema'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
        
        // Create or update schema
        register_rest_route($this->namespace, '/schemas', array(
            'methods' => 'POST',
            'callback' => array($this, 'create_schema'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
        
        // Update schema
        register_rest_route($this->namespace, '/schemas/(?P<id>\d+)', array(
            'methods' => 'PUT',
            'callback' => array($this, 'update_schema'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
        
        // Delete schema
        register_rest_route($this->namespace, '/schemas/(?P<id>\d+)', array(
            'methods' => 'DELETE',
            'callback' => array($this, 'delete_schema'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
        
        // Bulk create/update schemas
        register_rest_route($this->namespace, '/schemas/bulk', array(
            'methods' => 'POST',
            'callback' => array($this, 'bulk_update_schemas'),
            'permission_callback' => array($this, 'check_admin_permission')
        ));
    }
    
    /**
     * Check if user has admin permissions
     */
    public function check_admin_permission() {
        return current_user_can('manage_options');
    }
    
    /**
     * Get all schemas
     */
    public function get_schemas($request) {
        $params = $request->get_params();
        $object_id = isset($params['object_id']) ? intval($params['object_id']) : 0;
        $object_type = isset($params['object_type']) ? sanitize_text_field($params['object_type']) : '';
        
        if ($object_id && $object_type) {
            $schemas = $this->schema_manager->get_schemas_for_object($object_id, $object_type);
        } else {
            // Get all schemas (admin only)
            $schemas = $this->schema_manager->get_all_schemas();
        }
        
        return rest_ensure_response($schemas);
    }
    
    /**
     * Get schema by ID
     */
    public function get_schema($request) {
        $schema_id = $request['id'];
        $schema = $this->schema_manager->get_schema($schema_id);
        
        if (empty($schema)) {
            return new WP_Error('schema_not_found', 'Schema not found', array('status' => 404));
        }
        
        return rest_ensure_response($schema);
    }
    
    /**
     * Create schema
     */
    public function create_schema($request) {
        $params = $request->get_params();
        
        // Validate required fields
        if (!isset($params['object_id']) || !isset($params['object_type']) || 
            !isset($params['schema_type']) || !isset($params['schema_data'])) {
            return new WP_Error('missing_fields', 'Missing required fields', array('status' => 400));
        }
        
        $object_id = intval($params['object_id']);
        $object_type = sanitize_text_field($params['object_type']);
        $schema_type = sanitize_text_field($params['schema_type']);
        $schema_data = $params['schema_data'];
        
        // Validate schema data is valid JSON
        json_decode($schema_data);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return new WP_Error('invalid_json', 'Invalid JSON in schema_data', array('status' => 400));
        }
        
        $schema_id = $this->schema_manager->save_schema($object_id, $object_type, $schema_type, $schema_data);
        
        if (!$schema_id) {
            return new WP_Error('schema_save_failed', 'Failed to save schema', array('status' => 500));
        }
        
        $schema = $this->schema_manager->get_schema($schema_id);
        return rest_ensure_response($schema);
    }
    
    /**
     * Update schema
     */
    public function update_schema($request) {
        $schema_id = $request['id'];
        $params = $request->get_params();
        
        // Validate required fields
        if (!isset($params['schema_data'])) {
            return new WP_Error('missing_fields', 'Missing required fields', array('status' => 400));
        }
        
        $schema_data = $params['schema_data'];
        
        // Validate schema data is valid JSON
        json_decode($schema_data);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return new WP_Error('invalid_json', 'Invalid JSON in schema_data', array('status' => 400));
        }
        
        $success = $this->schema_manager->update_schema($schema_id, $schema_data);
        
        if (!$success) {
            return new WP_Error('schema_update_failed', 'Failed to update schema', array('status' => 500));
        }
        
        $schema = $this->schema_manager->get_schema($schema_id);
        return rest_ensure_response($schema);
    }
    
    /**
     * Delete schema
     */
    public function delete_schema($request) {
        $schema_id = $request['id'];
        $success = $this->schema_manager->delete_schema($schema_id);
        
        if (!$success) {
            return new WP_Error('schema_delete_failed', 'Failed to delete schema', array('status' => 500));
        }
        
        return rest_ensure_response(array('deleted' => true));
    }
    
    /**
     * Bulk update schemas
     */
    public function bulk_update_schemas($request) {
        $params = $request->get_params();
        
        if (!isset($params['schemas']) || !is_array($params['schemas'])) {
            return new WP_Error('missing_fields', 'Missing required fields', array('status' => 400));
        }
        
        $schemas = $params['schemas'];
        $results = array(
            'success' => array(),
            'errors' => array()
        );
        
        foreach ($schemas as $schema) {
            // Validate required fields
            if (!isset($schema['object_id']) || !isset($schema['object_type']) || 
                !isset($schema['schema_type']) || !isset($schema['schema_data'])) {
                $results['errors'][] = array(
                    'message' => 'Missing required fields',
                    'schema' => $schema
                );
                continue;
            }
            
            $object_id = intval($schema['object_id']);
            $object_type = sanitize_text_field($schema['object_type']);
            $schema_type = sanitize_text_field($schema['schema_type']);
            $schema_data = $schema['schema_data'];
            
            // Validate schema data is valid JSON
            json_decode($schema_data);
            if (json_last_error() !== JSON_ERROR_NONE) {
                $results['errors'][] = array(
                    'message' => 'Invalid JSON in schema_data',
                    'schema' => $schema
                );
                continue;
            }
            
            $schema_id = $this->schema_manager->save_schema($object_id, $object_type, $schema_type, $schema_data);
            
            if (!$schema_id) {
                $results['errors'][] = array(
                    'message' => 'Failed to save schema',
                    'schema' => $schema
                );
            } else {
                $results['success'][] = array(
                    'schema_id' => $schema_id,
                    'object_id' => $object_id,
                    'object_type' => $object_type
                );
            }
        }
        
        return rest_ensure_response($results);
    }
}
```

## 8. Python Script to Upload Schema Data

Create a Python script to upload the generated Schema data to WordPress:

```python
import requests
import json
import pandas as pd
import time
from requests.auth import HTTPBasicAuth

# WordPress REST API credentials - Use application passwords
WP_API_USER = 'your_username'
WP_API_PASSWORD = 'your_app_password'

# WordPress REST API endpoint for our custom plugin
WP_API_SCHEMA_ENDPOINT = 'https://webmemo.ch/wp-json/webmemo-schema/v1/schemas/bulk'

# Load the schema data from Google Sheets or local file
schemas_df = pd.read_csv('webmemo_schemas.csv')

# Prepare the data for the bulk update
schemas = []
for _, row in schemas_df.iterrows():
    schemas.append({
        'object_id': int(row['object_id']),
        'object_type': row['object_type'],
        'schema_type': row['schema_type'],
        'schema_data': row['schema_data']  # This should be a valid JSON string
    })

# Split into batches of 50 to avoid timeouts and memory issues
batch_size = 50
for i in range(0, len(schemas), batch_size):
    batch = schemas[i:i+batch_size]
    
    # Send the batch to WordPress
    response = requests.post(
        WP_API_SCHEMA_ENDPOINT,
        auth=HTTPBasicAuth(WP_API_USER, WP_API_PASSWORD),
        json={'schemas': batch}
    )
    
    # Check the response
    if response.status_code == 200:
        result = response.json()
        print(f"Batch {i//batch_size + 1}: Uploaded {len(result['success'])} schemas, {len(result['errors'])} errors")
        
        # Print errors for debugging
        if len(result['errors']) > 0:
            for error in result['errors']:
                print(f"  Error: {error['message']}")
    else:
        print(f"Batch {i//batch_size + 1}: Failed with status {response.status_code}")
        print(response.text)
    
    # Sleep to avoid overwhelming the server
    time.sleep(1)

print("Schema upload complete!")
```

## 9. Validation Script

Create a script to validate your Schema implementations:

```python
import requests
import json
import pandas as pd
from bs4 import BeautifulSoup
import re

# Google's Structured Data Testing Tool API (Note: This is now deprecated, 
# but included for reference. Use Rich Results Test API instead)
SCHEMA_VALIDATOR_URL = 'https://search.google.com/test/rich-results/result'

# List of URLs to validate
urls = [
    'https://webmemo.ch',
    'https://webmemo.ch/kontakt-ueber-mich-walter-schaerer',
    # Add more URLs as needed
]

results = []

for url in urls:
    print(f"Validating {url}...")
    
    # Fetch the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract all Schema.org JSON-LD scripts
    schema_scripts = soup.find_all('script', {'type': 'application/ld+json'})
    
    # Parse and validate each script
    for i, script in enumerate(schema_scripts):
        try:
            # Parse the JSON
            schema_data = json.loads(script.string)
            
            # Extract the Schema type
            schema_type = schema_data.get('@type', 'Unknown')
            
            # Identify the page type
            page_type = 'Home Page' if url == 'https://webmemo.ch' else url.split('/')[-1]
            
            # Add to results
            results.append({
                'url': url,
                'page_type': page_type,
                'schema_index': i,
                'schema_type': schema_type,
                'valid_json': True,
                'schema_data': json.dumps(schema_data)
            })
            
        except json.JSONDecodeError:
            results.append({
                'url': url,
                'page_type': page_type,
                'schema_index': i,
                'schema_type': 'Invalid JSON',
                'valid_json': False,
                'schema_data': script.string
            })
    
    # Sleep to avoid too many requests
    time.sleep(1)

# Convert to DataFrame for analysis
results_df = pd.DataFrame(results)

# Save results for review
results_df.to_csv('schema_validation_results.csv', index=False)

print(f"Validation complete! Found {len(results)} Schema.org implementations across {len(urls)} URLs.")
print(f"Valid JSON: {results_df['valid_json'].sum()} / {len(results_df)}")
```

## 10. Monitoring and Updates

Set up a GitHub Actions workflow to regularly check and update your Schema implementations:

```yaml
name: Schema.org Update

on:
  schedule:
    - cron: '0 0 * * 0'  # Run every Sunday at midnight
  workflow_dispatch:     # Allow manual triggers

jobs:
  update-schema:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests pandas beautifulsoup4
    
    - name: Run schema extraction
      run: python scripts/extract_data.py
    
    - name: Generate schema
      run: python scripts/generate_schema.py
    
    - name: Validate schema
      run: python scripts/validate_schema.py
    
    - name: Upload schema to WordPress
      run: python scripts/upload_schema.py
    
    - name: Commit changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add data/
        git commit -m "Update Schema.org data" || echo "No changes to commit"
        git push
```

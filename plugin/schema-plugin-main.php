<?php
/**
 * Plugin Name: Webmemo Schema.org
 * Description: Advanced Schema.org implementation for Webmemo.ch
 * Version: 1.0.0
 * Author: Walter Schärer
 * Author URI: https://webmemo.ch/author/walter-schaerer
 * Text Domain: webmemo-schema
 * Domain Path: /languages
 */

// Exit if accessed directly
if (!defined('ABSPATH')) {
    exit;
}

// Define plugin constants
define('WEBMEMO_SCHEMA_VERSION', '1.0.0');
define('WEBMEMO_SCHEMA_PATH', plugin_dir_path(__FILE__));
define('WEBMEMO_SCHEMA_URL', plugin_dir_url(__FILE__));
define('WEBMEMO_SCHEMA_FILE', __FILE__);

/**
 * Main Webmemo Schema Class
 */
class Webmemo_Schema {
    /**
     * Instance of this class
     */
    private static $instance = null;

    /**
     * Get instance of this class
     */
    public static function get_instance() {
        if (null === self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    /**
     * Constructor
     */
    private function __construct() {
        // Include required files
        $this->includes();
        
        // Initialize components
        add_action('plugins_loaded', array($this, 'init'));
        
        // Register activation and deactivation hooks
        register_activation_hook(WEBMEMO_SCHEMA_FILE, array($this, 'activate'));
        register_deactivation_hook(WEBMEMO_SCHEMA_FILE, array($this, 'deactivate'));
    }

    /**
     * Include required files
     */
    private function includes() {
        // Core classes
        require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-db.php';
        require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-types.php';
        require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-generator.php';
        require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-manager.php';
        
        // REST API
        require_once WEBMEMO_SCHEMA_PATH . 'includes/class-schema-rest-api.php';
        
        // Admin area
        if (is_admin()) {
            require_once WEBMEMO_SCHEMA_PATH . 'admin/class-schema-admin.php';
        }
    }

    /**
     * Initialize components
     */
    public function init() {
        // Initialize REST API
        $rest_api = new Webmemo_Schema_REST_API();
        
        // Initialize admin interface if in admin area
        if (is_admin()) {
            $admin = new Webmemo_Schema_Admin();
        }
        
        // Add Schema to head
        add_action('wp_head', array($this, 'add_schema_to_head'), 99);
        
        // Load translations
        load_plugin_textdomain('webmemo-schema', false, dirname(plugin_basename(WEBMEMO_SCHEMA_FILE)) . '/languages');
    }

    /**
     * Plugin activation
     */
    public function activate() {
        // Create database tables
        $schema_db = new Webmemo_Schema_DB();
        $schema_db->create_tables();
        
        // Set version
        update_option('webmemo_schema_version', WEBMEMO_SCHEMA_VERSION);
        
        // Clear rewrite rules
        flush_rewrite_rules();
    }

    /**
     * Plugin deactivation
     */
    public function deactivate() {
        // Clear rewrite rules
        flush_rewrite_rules();
    }

    /**
     * Add Schema.org markup to head
     */
    public function add_schema_to_head() {
        $schema_manager = new Webmemo_Schema_Manager();
        $schema_data = $schema_manager->get_schema_for_current_page();
        
        if (!empty($schema_data)) {
            foreach ($schema_data as $schema) {
                echo '<script type="application/ld+json">' . $schema . '</script>' . "\n";
            }
        }
    }
}

// Initialize the plugin
function webmemo_schema() {
    return Webmemo_Schema::get_instance();
}

// Start the plugin
webmemo_schema();
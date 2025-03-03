<?php
/**
 * Schema Database Class
 */
class Webmemo_Schema_DB {
    /**
     * Table name
     */
    private $table_name;

    /**
     * Constructor
     */
    public function __construct() {
        global $wpdb;
        $this->table_name = $wpdb->prefix . 'webmemo_schema';
    }

    /**
     * Create database tables
     */
    public function create_tables() {
        global $wpdb;
        
        $charset_collate = $wpdb->get_charset_collate();
        
        $sql = "CREATE TABLE {$this->table_name} (
            schema_id BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            object_id BIGINT(20) UNSIGNED NOT NULL,
            object_type VARCHAR(50) NOT NULL,
            schema_type VARCHAR(50) NOT NULL,
            schema_data LONGTEXT NOT NULL,
            last_updated DATETIME NOT NULL,
            PRIMARY KEY (schema_id),
            KEY object_id (object_id),
            KEY object_type (object_type),
            KEY schema_type (schema_type)
        ) $charset_collate;";
        
        require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
        dbDelta($sql);
    }

    /**
     * Get all schemas
     */
    public function get_all_schemas() {
        global $wpdb;
        
        $sql = "SELECT * FROM {$this->table_name} ORDER BY object_type, object_id";
        
        $results = $wpdb->get_results($sql, ARRAY_A);
        
        return $this->maybe_decode_schema_data($results);
    }

    /**
     * Get schema by ID
     */
    public function get_schema($schema_id) {
        global $wpdb;
        
        $sql = $wpdb->prepare(
            "SELECT * FROM {$this->table_name} WHERE schema_id = %d",
            $schema_id
        );
        
        $result = $wpdb->get_row($sql, ARRAY_A);
        
        return $this->maybe_decode_schema_data($result);
    }

    /**
     * Get schemas by object
     */
    public function get_schemas_by_object($object_id, $object_type) {
        global $wpdb;
        
        $sql = $wpdb->prepare(
            "SELECT * FROM {$this->table_name} WHERE object_id = %d AND object_type = %s",
            $object_id,
            $object_type
        );
        
        $results = $wpdb->get_results($sql, ARRAY_A);
        
        return $this->maybe_decode_schema_data($results);
    }

    /**
     * Get schemas by type
     */
    public function get_schemas_by_type($schema_type) {
        global $wpdb;
        
        $sql = $wpdb->prepare(
            "SELECT * FROM {$this->table_name} WHERE schema_type = %s",
            $schema_type
        );
        
        $results = $wpdb->get_results($sql, ARRAY_A);
        
        return $this->maybe_decode_schema_data($results);
    }

    /**
     * Get global schemas (WebSite, Organization, etc.)
     */
    public function get_global_schemas() {
        return $this->get_schemas_by_object(0, 'global');
    }

    /**
     * Save schema
     */
    public function save_schema($object_id, $object_type, $schema_type, $schema_data) {
        global $wpdb;
        
        // Check if schema already exists
        $existing = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT schema_id FROM {$this->table_name} WHERE object_id = %d AND object_type = %s AND schema_type = %s",
                $object_id,
                $object_type,
                $schema_type
            )
        );
        
        if ($existing) {
            // Update existing schema
            $result = $wpdb->update(
                $this->table_name,
                array(
                    'schema_data' => $schema_data,
                    'last_updated' => current_time('mysql')
                ),
                array('schema_id' => $existing->schema_id),
                array('%s', '%s'),
                array('%d')
            );
            
            return $result ? $existing->schema_id : false;
        } else {
            // Insert new schema
            $result = $wpdb->insert(
                $this->table_name,
                array(
                    'object_id' => $object_id,
                    'object_type' => $object_type,
                    'schema_type' => $schema_type,
                    'schema_data' => $schema_data,
                    'last_updated' => current_time('mysql')
                ),
                array('%d', '%s', '%s', '%s', '%s')
            );
            
            return $result ? $wpdb->insert_id : false;
        }
    }

    /**
     * Update schema
     */
    public function update_schema($schema_id, $schema_data) {
        global $wpdb;
        
        $result = $wpdb->update(
            $this->table_name,
            array(
                'schema_data' => $schema_data,
                'last_updated' => current_time('mysql')
            ),
            array('schema_id' => $schema_id),
            array('%s', '%s'),
            array('%d')
        );
        
        return $result !== false;
    }

    /**
     * Delete schema
     */
    public function delete_schema($schema_id) {
        global $wpdb;
        
        $result = $wpdb->delete(
            $this->table_name,
            array('schema_id' => $schema_id),
            array('%d')
        );
        
        return $result !== false;
    }

    /**
     * Delete schemas by object
     */
    public function delete_schemas_by_object($object_id, $object_type) {
        global $wpdb;
        
        $result = $wpdb->delete(
            $this->table_name,
            array(
                'object_id' => $object_id,
                'object_type' => $object_type
            ),
            array('%d', '%s')
        );
        
        return $result !== false;
    }

    /**
     * Maybe decode schema data
     */
    private function maybe_decode_schema_data($data) {
        if (empty($data)) {
            return $data;
        }
        
        if (is_array($data) && isset($data[0])) {
            // Array of schemas
            foreach ($data as &$schema) {
                if (isset($schema['schema_data'])) {
                    $schema['schema_data_decoded'] = json_decode($schema['schema_data'], true);
                }
            }
        } else {
            // Single schema
            if (isset($data['schema_data'])) {
                $data['schema_data_decoded'] = json_decode($data['schema_data'], true);
            }
        }
        
        return $data;
    }
}
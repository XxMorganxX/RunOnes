import os
import sys
from contextlib import contextmanager
from supabase import create_client, Client
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config


class SupabaseDB:
    """
    Supabase Database wrapper class for managing database operations
    """
    
    _instance = None
    _client: Client = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super(SupabaseDB, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the Supabase connection"""
        if self._client is None:
            load_dotenv()
            self._connect()
    
    def _connect(self):
        """
        Establish connection to Supabase
        
        Raises:
            ValueError: If SUPABASE_URL or SUPABASE_KEY are not set
        """
        supabase_url = config.SUPABASE_URL
        supabase_key = config.SUPABASE_KEY
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
            )
        
        self._client = create_client(supabase_url, supabase_key)
    
    @property
    def client(self) -> Client:
        """
        Get the Supabase client instance
        
        Returns:
            Client: Supabase client instance
        """
        if self._client is None:
            self._connect()
        return self._client
    
    def query_table(self, table_name: str, **filters):
        """
        Query a table with optional filters
        
        Args:
            table_name: Name of the table to query
            **filters: Column filters (e.g., id=1, status='active')
        
        Returns:
            dict: Query response with data
        """
        query = self.client.table(table_name).select("*")
        
        for key, value in filters.items():
            query = query.eq(key, value)
        
        response = query.execute()
        return response.data
    
    def insert_record(self, table_name: str, data: dict):
        """
        Insert a record into a table
        
        Args:
            table_name: Name of the table
            data: Dictionary containing the data to insert
        
        Returns:
            dict: Insert response with data
        """
        response = self.client.table(table_name).insert(data).execute()
        return response.data
    
    def update_record(self, table_name: str, record_id: int, data: dict):
        """
        Update a record in a table
        
        Args:
            table_name: Name of the table
            record_id: ID of the record to update
            data: Dictionary containing the data to update
        
        Returns:
            dict: Update response with data
        """
        response = self.client.table(table_name).update(data).eq('id', record_id).execute()
        return response.data
    
    def update_by(self, table_name: str, column: str, value, data: dict):
        """
        Update a record in a table by a custom column
        
        Args:
            table_name: Name of the table
            column: Column name to filter by
            value: Value to match
            data: Dictionary containing the data to update
        
        Returns:
            dict: Update response with data
        """
        response = self.client.table(table_name).update(data).eq(column, value).execute()
        return response.data
    
    def delete_record(self, table_name: str, record_id: int):
        """
        Delete a record from a table
        
        Args:
            table_name: Name of the table
            record_id: ID of the record to delete
        
        Returns:
            dict: Delete response
        """
        response = self.client.table(table_name).delete().eq('id', record_id).execute()
        return response.data
    
    def select(self, table_name: str, columns: str = "*"):
        """
        Get a query builder for more complex queries
        
        Args:
            table_name: Name of the table
            columns: Columns to select (default: "*")
        
        Returns:
            Query builder object
        
        Example:
            db = SupabaseDB()
            results = db.select("users", "id, name, email").eq("status", "active").execute()
        """
        return self.client.table(table_name).select(columns)
    
    def is_connected(self) -> bool:
        """
        Check if the database connection is established
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._client is not None
    
    @contextmanager
    def transaction(self):
        """
        Context manager for handling database transactions with rollback.
        Stores changes and rolls back if any operation fails.
        
        Usage:
            with db.transaction() as tx:
                tx.update_by("users", "user_uid", user_id, {"elo": 1500})
                tx.update_record("match_tx", match_id, {"is_complete": True})
        """
        transaction = DatabaseTransaction(self)
        try:
            yield transaction
            # If we get here, all operations succeeded
            transaction.commit()
        except Exception as e:
            # Rollback all changes
            transaction.rollback()
            raise e


class DatabaseTransaction:
    """Handles transactional operations with rollback capability"""
    
    def __init__(self, db: SupabaseDB):
        self.db = db
        self.operations = []
        self.original_values = []
    
    def update_by(self, table_name: str, column: str, value, data: dict):
        """Update by column with transaction support"""
        # Fetch original value before update
        original = self.db.client.table(table_name).select("*").eq(column, value).execute()
        
        if original.data:
            self.original_values.append({
                'table': table_name,
                'column': column,
                'value': value,
                'original': original.data[0]
            })
        
        # Perform the update
        result = self.db.update_by(table_name, column, value, data)
        self.operations.append(('update_by', table_name, column, value, data))
        return result
    
    def update_record(self, table_name: str, record_id: int, data: dict):
        """Update record with transaction support"""
        # Fetch original value before update
        original = self.db.client.table(table_name).select("*").eq('id', record_id).execute()
        
        if original.data:
            self.original_values.append({
                'table': table_name,
                'column': 'id',
                'value': record_id,
                'original': original.data[0]
            })
        
        # Perform the update
        result = self.db.update_record(table_name, record_id, data)
        self.operations.append(('update_record', table_name, record_id, data))
        return result
    
    def commit(self):
        """Commit transaction (no-op for now, changes already applied)"""
        self.operations.clear()
        self.original_values.clear()
    
    def rollback(self):
        """Rollback all changes to original values"""
        for item in reversed(self.original_values):
            try:
                # Restore original values
                self.db.client.table(item['table']).update(
                    item['original']
                ).eq(item['column'], item['value']).execute()
            except Exception as rollback_error:
                print(f"Rollback error for {item['table']}: {rollback_error}")


# Convenience functions for backward compatibility
def init_supabase() -> SupabaseDB:
    """
    Initialize and return SupabaseDB instance
    
    Returns:
        SupabaseDB: Database instance
    """
    return SupabaseDB()


def get_supabase() -> SupabaseDB:
    """
    Get the SupabaseDB instance
    
    Returns:
        SupabaseDB: Database instance
    """
    return SupabaseDB()


def query_table(table_name: str, **filters):
    """Query a table with optional filters (backward compatible)"""
    db = SupabaseDB()
    return db.query_table(table_name, **filters)


def insert_record(table_name: str, data: dict):
    """Insert a record into a table (backward compatible)"""
    db = SupabaseDB()
    return db.insert_record(table_name, data)


def update_record(table_name: str, record_id: int, data: dict):
    """Update a record in a table (backward compatible)"""
    db = SupabaseDB()
    return db.update_record(table_name, record_id, data)


def delete_record(table_name: str, record_id: int):
    """Delete a record from a table (backward compatible)"""
    db = SupabaseDB()
    return db.delete_record(table_name, record_id)


if __name__ == "__main__":
    # Test the connection
    db = SupabaseDB()
    print("✓ Supabase connected successfully")
    print(f"Connection status: {db.is_connected()}")
    
    # Example usage
    try:
        users = db.query_table("users")
        print(f"Found {len(users)} users")
    except Exception as e:
        print(f"Error querying users: {e}")

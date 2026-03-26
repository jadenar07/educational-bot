import psycopg2
from psycopg2 import pool
import os
from psycopg2.extras import RealDictCursor #changes fetch returns to a dict
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostgresCRUD():
    _pool = None  # Class variable to store pool
    
    @classmethod
    def init_pool(cls):
        """Initialize connection pool once at startup"""
        if cls._pool is None:
            cls._pool = pool.SimpleConnectionPool(
                1,  # Minimum 1 connection
                20,  # Maximum 20 connections
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                cursor_factory=RealDictCursor
            )
            logger.info("Connection pool initialized (1-20 connections)")
    
    def get_connection(self):
        """Get connection from pool"""
        self.init_pool()
        try:
            connection = self._pool.getconn()
            logger.info("Got connection from pool")
            return connection
        except pool.PoolError:
            logger.error("No available connections in pool")
            raise
    
    @staticmethod
    def return_connection(db):
        """Return connection to pool"""
        if PostgresCRUD._pool:
            PostgresCRUD._pool.putconn(db)
            logger.info("Returned connection to pool")
    
    async def ping(self):
        """Simple health check - tests database connectivity."""
        db = None
        try:
            db = self.get_connection()
            with db.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            return True
        except Exception as e:
            logger.error(f"Postgres ping failed: {e}")
            raise
        finally:
            if db:
                self.return_connection(db)
    
    def create_user(self, db, username, email, role, default_collection=None):
        valid_roles = {"ta", "student", "professor", "admin"}
        if role not in valid_roles:
            logger.error(f"Invalid role provided: {role}")
            return {"success": False, "error": "Invalid role"}
        try:
            with db.cursor() as cur:
                cur.execute("""
                    INSERT INTO profiles.users (username, email, role, default_collection)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (username, email, role, default_collection))
                user_id = cur.fetchone()["id"]
                db.commit()
                logger.info(f"User created with ID: {user_id}")
                return {"success": True, "message": "User created successfully!", "data": user_id}
        except psycopg2.Error as e:
            logger.error(f"Error creating user: {e}")
            return {"success": False, "error": "User creation failed", "details": str(e)}

    def get_user(self, db, user_id: int | None = None, email: str | None = None, username: str | None = None):
        candidates = []
        user = None
        allowed_fields = {"id", "email", "username"}
        if user_id is not None:
            candidates.append(("id", user_id))
        if email is not None:
            candidates.append(("email", email))
        if username is not None:
            candidates.append(("username", username))

        if not candidates:
            logger.warning("No valid identifier provided for get_user")
            return {"success": False, "error": "Provide user_id, email, or username"}

        try:
            with db.cursor() as cur:
                for field, value in candidates:
                    if field in allowed_fields:
                        cur.execute(f"SELECT * FROM profiles.users WHERE {field} = %s;", (value,))
                        user = cur.fetchone()
                        if user is not None:
                            return {"success": True, "data": user}
        except psycopg2.Error as e:
            logger.error(f"Error fetching user: {e}")
            return {"success": False, "error": "Database query failed", "details": str(e)}

        return {"success": False, "error": "User not found"}

    def update_user(self, db, user_id, new_data):
        allowed_fields = {"email", "username", "role", "default_collection"}
        new_data = {k: v for k, v in new_data.items() if k in allowed_fields}
        if not new_data:
            logger.warning("No valid fields provided for update_user")
            return {"success": False, "error": "No valid fields to update"}
        try:
            with db.cursor() as cur:
                set_clause = ", ".join([f"{key} = %s" for key in new_data.keys()])
                values = list(new_data.values())
                values.append(user_id)

                query = f"UPDATE profiles.users SET {set_clause} WHERE id = %s RETURNING *;"
                cur.execute(query, values)
                updated = cur.fetchone()
                db.commit()
                if updated is None:
                    logger.warning(f"User with ID {user_id} not found for update")
                    return {"success": False, "error": "User not found"}
                
                logger.info(f"User with ID {user_id} updated successfully")
                return {"success": True, "message": "User updated successfully!", "data": updated}
        except psycopg2.Error as e:
            logger.error(f"Error updating user: {e}")
            return {"success": False, "error": "Update failed", "details": str(e)}

    def delete_user(self, db, user_id):
        try:
            with db.cursor() as cur:
                cur.execute("""
                    DELETE FROM profiles.users WHERE id = %s RETURNING id;
                """, (user_id,))
                deleted = cur.fetchone()
                db.commit()
                if deleted is None:
                    logger.warning(f"User with ID {user_id} not found for deletion") 
                    return {"success": False, "error": "User not found"}
                logger.info(f"User with ID {user_id} deleted successfully")
            return {"success": True, "message": "User deleted successfully!", "data": deleted}
        except psycopg2.Error as e:
            logger.error(f"Error deleting user: {e}")
            return {"success": False, "error": "Deletion failed", "details": str(e)}

import psycopg2
import os
from psycopg2.extras import RealDictCursor #changes fetch returns to a dict
from dotenv import load_dotenv
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PostgresCRUD():
    def get_connection(self):
        load_dotenv()
        try:
            connection = psycopg2.connect(
                dbname = os.getenv("POSTGRES_DB"),
                user = os.getenv("POSTGRES_USER"),
                password = os.getenv("POSTGRES_PASSWORD"),
                host = os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection established")
            return connection
        except psycopg2.Error as e: 
            logger.error(f"Error connecting to database: {e}")
            raise

    def create_user(self, db, username, email, role, default_collection=None):
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
            logger.error(f" Error creating user: {e}")
            return {"success": False, "error": "User creation failed", "details": str(e)}

    def get_user(self, db, user_id: int | None = None, email: str | None = None, username: str | None = None):
        candidates = []
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
                    return {"success": False, "error": "User not found"}
                logger.info(f"User with ID {user_id} deleted successfully")
            return {"success": True, "message": "User deleted successfully!", "data": deleted}
        except psycopg2.Error as e:
            logger.error(f"Error deleting user: {e}")
            return {"success": False, "error": "Deletion failed", "details": str(e)}

import psycopg2
from psycopg2.extras import RealDictCursor #changes fetch returns to a dict

class PostgresCRUD():
    def get_connection(self):
        return psycopg2.connect(
            dbname = "postgres",
            user ="marc",
            password = "fams25266",
            host = "localhost",
            port="5432",
            cursor_factory=RealDictCursor
        )


    def create_user(self, db, username, email, role, default_collection=None):
        with db.cursor() as cur:
            #lowkey could downsize this into one...
            if default_collection:
                cur.execute("""
                    INSERT INTO profiles.users (username, email, role, default_collection)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (username, email, role, default_collection))
            else:
                cur.execute("""
                    INSERT INTO profiles.users (username, email, role)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                """, (username, email, role)
                )

            user_id = cur.fetchone()["id"]
            db.commit()
            return {"id": user_id, "message": "User created successfully!"}

    def get_user(self, db, user_id: int | None = None, email: str | None = None, username: str | None = None):
        # Build an ordered list of candidate lookups
        candidates = []
        if user_id is not None:
            candidates.append(("id", user_id))
        if email is not None:
            candidates.append(("email", email))
        if username is not None:
            candidates.append(("username", username))

        if not candidates:
            return {"error": "Provide user_id, email, or username"}

        try:
            with db.cursor() as cur:
                for field, value in candidates:
                    cur.execute(f"SELECT * FROM profiles.users WHERE {field} = %s;", (value,))
                    user = cur.fetchone()
                    if user is not None:
                        return user

        except psycopg2.Error as e:
            # This is a real DB error (syntax, connection, etc.)
            return {"error": "Database query failed", "details": str(e)}

        return {"error": "User not found"}

        
    def update_user(self, db, user_id, new_data):
        with db.cursor() as cur:
            # Create a list of field assignments like "email = %s"
            set_clause = ", ".join([f"{key} = %s" for key in new_data.keys()])
            values = list(new_data.values())
            values.append(user_id)

            query = f"UPDATE profiles.users SET {set_clause} WHERE id = %s RETURNING *;"
            cur.execute(query, values)
            updated = cur.fetchone()
            db.commit()
            return updated


    def delete_user(self, db, user_id, username=None):
        with db.cursor() as cur:
            cur.execute("""
                DELETE FROM profiles.users WHERE id = %s RETURNING id;
            """, (user_id,)
            )
            deleted = cur.fetchone()
            db.commit()
            if deleted:
                return {"id": user_id, "message": "User deleted successfully!"}
            else:
                return {"error": "User not found"}
    
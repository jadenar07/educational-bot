import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(
        dbname = "postgres",
        user ="marc",
        password = "fams25266",
        host = "localhost",
        port="5432",
        cursor_factory=RealDictCursor
    )


def create_user(db, username, email, role, default_collection=None):
    with db.cursor() as cur:
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

def get_user(db, user_id):
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM profiles.users WHERE id = %s;
        """), (user_id,)
        user = cur.fetchone()
        if not user:
            return {"error": "User not found"}
        return user
    
#id immutable, role can be Up, name can be Up, username can be updated
def update_user(db, user_id, new_data):
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


def delete_user(db, user_id):
    with db.cursor() as cur:
        cur.execute("""
            DELETE FROM profiles.users WHERE id = %s RETURNING id;
        """, (user_id,)
        )
        deleted = cur.fetchone()
        db.commit()
        if deleted:
            return {"id": user_id, "message": "User deleted successfully!"}
        return {"error": "User not found"}
  
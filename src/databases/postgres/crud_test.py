from crudPostgres import PostgresCRUD

postgres = PostgresCRUD()
db = postgres.get_connection()

def test_create_and_get_user():
    created = postgres.create_user(db,"marclikestocode", "mw4725@nyu.edu", "student")
    fetched = postgres.get_user(db, created["id"])
    assert fetched["email"] == "mw4725@nyu.edu"
    return fetched["id"]
def delete(id):
    delete = postgres.delete_user(db, id)

def main():
   delete(db,"1")
main()

from crudPostgres import PostgresCRUD
import pytest   

postgres = PostgresCRUD()

@pytest.fixture
def db():
    return postgres.get_connection()

@pytest.fixture
def created_user(db):
    created = postgres.create_user(db, "marclikestocode", "mw4725@nyu.edu", "student")
    return created

def test_get_user(db, created_user):
    user_id = created_user["data"]
    fetched = postgres.get_user(db, user_id=user_id)
    assert fetched['success'] is True
    assert fetched['data']['username'] == "marclikestocode"
    return fetched

def test_update_user(db, created_user):
    user_id = created_user['data']
    updated = postgres.update_user(db, user_id=user_id, new_data={"email": "johnprok@nyu.edu"})
    assert updated['success'] is True
    assert updated['data']['email'] == "johnprok@nyu.edu"
    return updated

def test_delete_user(db, created_user):
    user_id = created_user['data']
    deleted = postgres.delete_user(db, user_id=user_id)
    assert deleted['success'] is True
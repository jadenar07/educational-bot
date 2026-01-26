from crudPostgres import PostgresCRUD
import pytest

from dotenv import load_dotenv
import os
load_dotenv()

postgres = PostgresCRUD()
db = postgres.get_connection()

def test_create_and_get_user():
    created = postgres.create_user(db,"marclikestocode", "mw4725@nyu.edu", "student")
def test_get(id):
    fetched = postgres.get_user(db, id)
    return fetched

def update(db, id, data):
    x = postgres.update_user(db, id, data)
    return x

def main():
    #update(db, "1", {"email": "johnprok@nyu.edu"})
    #postgres.create_user(db, "slapitonme", "marcitoo@nyu.edu", "student")
    print(test_get(4)['data']['username'])
   
   
main()


#thoughts: want more robust getter, and create (if someone is alreday created)
#shouldn't just stop after that command. 


#havent wrote unit tests for these yet.
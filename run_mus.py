from database import Database

db = Database()
db.init_db()

check_id= db.search_firms('ром')
num =  int(check_id['id'][0])


account_id = int(1)
result = db.run_mus(num, account_id)

print("result",result)


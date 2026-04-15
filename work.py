
from database import Database
from Parser.parser import parse_1c_table



db = Database()
db.init_db()

# создаём фирму
firm_id = db.get_or_create_firm("ООО Ромашка")

# создаём проверку
check_id = db.add_check(
    firm_id=firm_id,
    period="2024 год",
    materiality=100000
)

# создаём счёт
account_id = db.add_account(
    check_id=check_id,
    name="акты подрядчика"
)



df = parse_1c_table(
    file_path="Parser/data/Реестр Акты подрядчика 2025 5_6.xls",
    id_col=2,
    date_col =3,
    amount_col=6,
    start_row=6,
    end_row=7496,
    extra_cols=[4, 11]
)

db.insert_entries(account_id=account_id, df=df)


account_id = db.add_account(
    check_id=check_id,
    name="ВВод в эксплуатацию"
)

df = parse_1c_table(
    file_path="Parser/data/Реестр ввод в экспл ОС.xls",
    id_col=2,
    date_col =3,
    amount_col=6,
    start_row=6,
    end_row=40,
    extra_cols=[4, 7]
)

db.insert_entries(account_id=account_id, df=df)



account_id = db.add_account(
    check_id=check_id,
    name="входящие услуги"
)


df = parse_1c_table(
    file_path="Parser/data/РЕЕСТР входящие услуги 7-12.2025.xls",
    id_col=1,
    date_col =3,
    amount_col=2,
    start_row=2,
    end_row=1910,
    extra_cols=[4, 5]
)

db.insert_entries(account_id=account_id, df=df)



account_id = db.add_account(
    check_id=check_id,
    name="выручка"
)


df = parse_1c_table(
    file_path="Parser/data/Реестр выручка 07-12.2025.xls",
    id_col=3,
    date_col =2,
    amount_col=9,
    start_row=2,
    end_row=207,
    extra_cols=[4, 10]
)


db.insert_entries(account_id=account_id, df=df)



account_id = db.add_account(
    check_id=check_id,
    name="поступление тов и усл 4кв 2025"
)

df = parse_1c_table(
    file_path="Parser/data/РЕЕСТР поступление тов и усл 4кв 2025.xls",
    id_col=4,
    date_col =5,
    amount_col=9,
    start_row=4,
    end_row=491,
    extra_cols=[2, 11]
)


db.insert_entries(account_id=account_id, df=df)


account_id = db.add_account(
    check_id=check_id,
    name="услуги вход"
)

df = parse_1c_table(
    file_path="Parser/data/Реестр услуги вход 7-12.2025.xls",
    id_col=3,
    date_col =1,
    amount_col=2,
    start_row=2,
    end_row=287,
    extra_cols=[4, 5]
)


db.insert_entries(account_id=account_id, df=df)
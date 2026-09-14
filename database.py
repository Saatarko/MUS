import os
from typing import Any

import duckdb
import math
import random
from datetime import datetime

import pandas as pd



class Database:
    def __init__(self, path= os.path.join(os.getcwd(), "audit.db")):
        self.conn = duckdb.connect(path)

    # ---------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ---------------------------
    def init_db(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS firms (
            id INTEGER,
            name TEXT UNIQUE
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER,
            firm_id INTEGER,
            risk TEXT,
            period TEXT,
            materiality DOUBLE,
            created_at TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER,
            check_id INTEGER,
            acc_desc_id INTEGER
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS account_desc (
            id INTEGER,
            name TEXT,
            description TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER,
            account_id INTEGER,
            doc_id TEXT,
            date TEXT,
            amount DOUBLE,
            note TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS base_results (
            id INTEGER,
            check_id INTEGER,
            account_id INTEGER,
            PM DOUBLE,
            n DOUBLE,
            h DOUBLE,
            high_value_sum DOUBLE,
            mus_sum DOUBLE,
            test_sum DOUBLE,
            coverage DOUBLE,
            messages TEXT,
            total DOUBLE,
            created_at TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER,
            base_results_id INTEGER,
            doc_id TEXT,
            date TEXT,
            amount DOUBLE,
            note TEXT,
            selection_type TEXT
        )
        """)

        # self.conn.execute("""
        #     ATTACH 'audit_old.db' AS old_db
        # """)
        #
        # self.conn.execute("""
        #     INSERT INTO account_desc (id, name, description)
        #     SELECT id, name, description
        #     FROM old_db.account_desc
        # """)
        #
        # self.conn.execute("""
        #     DETACH old_db
        # """)

    # ---------------------------
    # УДАЛЕНИЕ ДАННЫХ ПО СЧЁТУ
    # ---------------------------
    def clear_account_data(self, account_id: int):

        # -------------------------
        # 1. найти base_results_id
        # -------------------------
        base_ids = self.conn.execute("""
            SELECT id FROM base_results
            WHERE account_id = ?
        """, [account_id]).fetchall()

        base_ids = [row[0] for row in base_ids]

        # -------------------------
        # 2. удалить results
        # -------------------------
        if base_ids:
            self.conn.execute(f"""
                DELETE FROM results
                WHERE base_results_id IN ({','.join(map(str, base_ids))})
            """)

        # -------------------------
        # 3. удалить base_results
        # -------------------------
        self.conn.execute("""
            DELETE FROM base_results
            WHERE account_id = ?
        """, [account_id])

        # -------------------------
        # 4. удалить entries
        # -------------------------
        self.conn.execute("""
            DELETE FROM entries
            WHERE account_id = ?
        """, [account_id])

    def get_one_acc_desc(self, id: int):
        row = self.conn.execute("""
            SELECT name FROM account_desc WHERE id = ?
        """, [id]).fetchone()

        if not row:
            return None

        return {"id": id, "name": row[0], "description": row[1]}

    def acc_descs(self):
        return self.conn.execute("""
            SELECT id, name, description
            FROM account_desc
            ORDER BY name
        """).fetchall()
    # ---------------------------
    # СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
    # ---------------------------
    def save_results(self, df_sample, selection_type_map: dict):
        """
        df_sample: DataFrame с колонкой index = entry_id
        selection_type_map: dict {entry_id: "MUS"/"HIGH_VALUE"/"RANDOM"}
        """

        rows = []

        for entry_id in df_sample["id"]:
            rows.append((
                entry_id,
                selection_type_map.get(entry_id, "MUS"),
                datetime.now()
            ))

        self.conn.executemany("""
        INSERT INTO results (entry_id, selection_type, created_at)
        VALUES (?, ?, ?)
        """, rows)

    # ---------------------------
    # ПОЛУЧЕНИЕ ВЫБОРКИ
    # ---------------------------
    def get_results(self, account_id: int):

        # 1. берём последний расчет
        base = self.conn.execute("""
            SELECT *
            FROM base_results
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, [account_id]).fetchone()

        if not base:
            return None

        # превращаем в dict (удобно для GUI)
        columns = [desc[0] for desc in self.conn.description]
        base_dict = dict(zip(columns, base))

        base_id = base_dict["id"]

        # 2. получаем выборку
        sample_df = self.conn.execute("""
            SELECT 
                doc_id,
                date,
                note,
                amount,
                selection_type
            FROM results
            WHERE base_results_id = ?
            ORDER BY amount DESC
        """, [base_id]).df()

        # 3. возвращаем всё вместе
        return {
            "PM": base_dict["PM"],
            "n": base_dict["n"],
            "h": base_dict["h"],
            "coverage": base_dict["coverage"],
            "total": base_dict["total"],
            "high_value_sum": base_dict["high_value_sum"],
            "mus_sum": base_dict["mus_sum"],
            "test_sum": base_dict["test_sum"],
            "messages": base_dict["messages"],
            "sample": sample_df
        }

    def get_or_create_firm(self, name: str):
        existing = self.conn.execute("""
            SELECT id FROM firms WHERE name = ?
        """, [name]).fetchone()

        if existing:
            return existing[0], False  # False = уже была

        new_id = self.next_id("firms")

        self.conn.execute("""
            INSERT INTO firms (id, name)
            VALUES (?, ?)
        """, [new_id, name])

        return new_id, True

    def get_or_create_acc_desc(self, name: str, description: str) -> tuple[Any, bool] | tuple[int, bool]:
        existing = self.conn.execute("""
            SELECT id FROM account_desc 
            WHERE name = ?
        """, [name]).fetchone()

        if existing:
            return existing[0], False

        new_id = self.next_id("account_desc")

        self.conn.execute("""
                    INSERT INTO account_desc (id, name, description)
                    VALUES (?, ?, ?)
                """, [new_id, name, description])

        self.conn.commit()

        return new_id, True

    def get_or_create_account(self, check_id: int, acc_desc_id: int):

        existing = self.conn.execute("""
            SELECT id
            FROM accounts
            WHERE check_id = ? AND acc_desc_id = ?
        """, [check_id, acc_desc_id]).fetchone()

        if existing:
            return existing[0], False

        new_id = self.next_id("accounts")

        self.conn.execute("""
            INSERT INTO accounts (
                id,
                check_id,
                acc_desc_id
            )
            VALUES (?, ?, ?)
        """, [new_id, check_id, acc_desc_id])

        self.conn.commit()

        return new_id, True


    def get_firm(self, id: int):
        row = self.conn.execute("""
            SELECT name FROM firms WHERE id = ?
        """, [id]).fetchone()

        if not row:
            return None

        return {"id": id, "name": row[0]}

    def update_firm(self, id: int, new_name: str):
        existing = self.conn.execute("""
            SELECT id FROM firms
            WHERE name = ? AND id != ?
        """, [new_name, id]).fetchone()

        if existing:
            return False, "duplicate"

        self.conn.execute("""
            UPDATE firms
            SET name = ?
            WHERE id = ?
        """, [new_name, id])

        self.conn.commit()

        return True, None

    def update_check(self, id: int, period: str, risk: str, materiality: float) -> int:

        self.conn.execute("""
            UPDATE checks
            SET period = ?, 
                risk = ?, 
                materiality = ?, 
                created_at = ?
            WHERE id = ?
        """, [period, risk, materiality, datetime.now(), id])

        return True

    def update_acc(self, id: int, acc_desc_id: int) -> bool:
        self.conn.execute("""
            UPDATE accounts
            SET acc_desc_id = ?
            WHERE id = ?
        """, [acc_desc_id, id])

        return True

    def update_acc_desc(self, id: int, name: str, description: str) -> int:

        self.conn.execute("""
            UPDATE account_desc
            SET name = ?,
                description = ?
            WHERE id = ?
        """, [name, description, id])

        return True


    def get_firms(self):
        return self.conn.execute("""
            SELECT id, name FROM firms ORDER BY name
        """).fetchall()

    def search_firms(self, query: str):
        return self.conn.execute("""
            SELECT id, name
            FROM firms
            WHERE LOWER(TRIM(name)) LIKE LOWER(TRIM(?))
            ORDER BY name
        """, [f"%{query}%"]).fetchall()

    def get_checks(self, firm_id: int):
        return self.conn.execute("""
            SELECT id, period, materiality, created_at, risk
            FROM checks
            WHERE firm_id = ?
            ORDER BY created_at DESC
        """, [firm_id]).fetchall()

    def get_one_checks(self, checks_id: int):
        return self.conn.execute("""
            SELECT id, period, risk,materiality, created_at
            FROM checks
            WHERE id = ?
        """,[checks_id]).df()

    def acc_descs_nameonly(self):
        return self.conn.execute("""
            SELECT id, name
            FROM account_desc
            ORDER BY name
        """).fetchall()

    # ---------------------------
    # ПОЛУЧЕНИЕ СЫРЫХ ДАННЫХ
    # ---------------------------
    def get_entries(self, account_id: int):
        return self.conn.execute(f"""
        SELECT *
        FROM entries
        WHERE account_id = {account_id}
        ORDER BY amount
        """).fetchall()

    def get_accounts_byid(self, account_id: int):
        return self.conn.execute("""
            SELECT id, acc_desc_id
            FROM accounts
            WHERE id = ?
        """, [account_id]).df()

    def get_acc_desc_byid(self, acc_desc_id: int):
        return self.conn.execute("""
            SELECT id, name, description
            FROM account_desc
            WHERE id = ?
            ORDER BY name
        """, [acc_desc_id]).df()

    def get_acc_desc_by_name(self, name: int):
        return self.conn.execute("""
            SELECT id, name, description
            FROM account_desc
            WHERE name = ?
            ORDER BY name
        """, [name]).df()

    def get_accounts(self, check_id: int):

        return self.conn.execute("""
            SELECT
                a.id,
                ad.name
            FROM accounts a
            JOIN account_desc ad
                ON a.acc_desc_id = ad.id
            WHERE a.check_id = ?
            ORDER BY ad.name
        """, [check_id]).fetchall()

    def next_id(self, table: str) -> int:
        result = self.conn.execute(f"""
            SELECT COALESCE(MAX(id), 0) + 1
            FROM {table}
        """).fetchone()[0]

        return result

    def add_firm(self, name: str) -> int:
        new_id = self.next_id("firms")

        self.conn.execute("""
            INSERT INTO firms (id, name)
            VALUES (?, ?)
        """, [new_id, name])

        return new_id

    def add_check(self, firm_id: int, period: str, risk: str, materiality: float) -> int:
        from datetime import datetime

        new_id = self.next_id("checks")

        self.conn.execute("""
            INSERT INTO checks (id, firm_id, period, materiality, risk,created_at)
            VALUES (?, ?, ?, ?, ?,?)
        """, [new_id, firm_id, period, materiality,risk, datetime.now()])

        return new_id



    def insert_entries(self, account_id: int, df):
        self.clear_account_data(account_id)

        df = df.copy()
        df["account_id"] = account_id

        # 🔥 добавим entry id
        start_id = self.next_id("entries")
        df["id"] = range(start_id, start_id + len(df))

        df = df[["id", "account_id", "doc_id", "date", "amount", "note"]]

        self.conn.register("df_view", df)

        self.conn.execute("""
        INSERT INTO entries (id, account_id, doc_id, date, amount, note)
        SELECT id, account_id, doc_id, date, amount, note FROM df_view
        """)

    def run_mus(self, check_id: int, account_id: int, name: str):
        messages = []
        self.name = name

        risk_k = {
            "низкий": 1,
            "средний": 3,
            "высокий": 7,
            "проверка сплошным порядком": 10,
        }

        # -------------------------
        # 1. PM и риск
        # -------------------------
        pm = self.conn.execute("""
            SELECT materiality, risk
            FROM checks
            WHERE id = ?
        """, [check_id]).fetchone()

        if not pm:
            return {"error": "Check not found"}

        PM, risk = pm

        K = risk_k.get(str(risk).strip().lower())

        if K is None:
            return {
                "error": f"Неизвестный уровень риска: {risk}"
            }

        # -------------------------
        # 2. Entries
        # -------------------------
        df = self.conn.execute("""
            SELECT *
            FROM entries
            WHERE account_id = ?
        """, [account_id]).df()

        if df.empty:
            return {
                "PM": PM,
                "n": 0,
                "h": 0,
                "messages": ["Нет данных"]
            }

        df = df.sort_values("amount").reset_index(drop=True)
        df["amount_abs"] = df["amount"].abs()
        df = df.sort_values("amount_abs").reset_index(drop=True)

        total = df["amount_abs"].sum()

        # -------------------------
        # 3. HIGH VALUE
        # -------------------------
        high_value_df = df[df["amount_abs"] >= PM]
        high_value_sum = high_value_df["amount_abs"].sum()

        # =====================================================
        # 4. ПРОВЕРКА СПЛОШНЫМ ПОРЯДКОМ
        # =====================================================
        if K == 10:

            messages.append(
                "⚠ Проверка сплошным порядком. "
                "В выборку включены все записи исходной совокупности. "
                "Показатели MUS не применяются."
            )

            # В выборку идут ВСЕ записи
            sample_df = df.copy()

            sample_df["selection_type"] = (
                "Проверка сплошным порядком"
            )

            # Показатели MUS не применяются
            n = 0
            h = 0
            mus_sum = 0

        # =====================================================
        # 5. ОБЫЧНАЯ MUS
        # =====================================================
        else:

            # Исключаем элементы >= PM из MUS
            df_mus = df[df["amount_abs"] < PM].copy()

            # -------------------------
            # 5.1 FALLBACK
            # -------------------------
            if total <= PM:

                messages.append(
                    "⚠ Совокупность < PM → случайная выборка. "
                    "Показатели не имеют значения"
                )

                sample_df = df.sample(
                    n=min(5, len(df))
                ).copy()

                sample_df["selection_type"] = (
                    "Случайная выборка"
                )

                n = 0
                h = 0

                mus_sum = sample_df["amount_abs"].sum()

            # -------------------------
            # 5.2 MUS
            # -------------------------
            else:

                total_mus = df_mus["amount_abs"].sum()

                if total_mus == 0:

                    mus_df = pd.DataFrame(
                        columns=df.columns
                    )

                    mus_sum = 0
                    n = 0
                    h = 0

                else:

                    n = math.ceil(
                        K * total_mus / PM
                    )

                    h = total_mus / n

                    start = random.uniform(0, h)

                    df_mus["cum_sum"] = (
                        df_mus["amount_abs"].cumsum()
                    )

                    sample_indices = []
                    current_point = start

                    while current_point < total_mus:
                        idx = df_mus[
                            df_mus["cum_sum"] >= current_point
                            ].index[0]

                        sample_indices.append(idx)

                        current_point += h

                    mus_df = df_mus.loc[
                        sample_indices
                    ].copy()

                    mus_df = mus_df.drop_duplicates(
                        subset=["id"]
                    )

                    mus_df["selection_type"] = (
                        "Выборка MUS"
                    )

                    mus_sum = mus_df["amount_abs"].sum()

                # -------------------------
                # объединяем HIGH VALUE + MUS
                # -------------------------
                high_value_df = high_value_df.copy()

                high_value_df["selection_type"] = (
                    "Выше уровня существенности"
                )

                sample_df = pd.concat(
                    [
                        high_value_df,
                        mus_df
                    ],
                    ignore_index=True
                )

        # -------------------------
        # 6. Итоги
        # -------------------------
        test_sum = sample_df["amount"].sum()

        coverage = (
            test_sum / total * 100
            if total > 0
            else 0
        )

        # -------------------------
        # 7. Очистка старых результатов
        # -------------------------
        self.conn.execute("""
            DELETE FROM base_results
            WHERE check_id = ?
              AND account_id = ?
        """, [check_id, account_id])

        # -------------------------
        # 8. Запись base_results
        # -------------------------
        now = datetime.now()

        base_id = self.next_id("base_results")

        self.conn.execute("""
            INSERT INTO base_results (
                id,
                check_id,
                account_id,
                PM,
                n,
                h,
                high_value_sum,
                mus_sum,
                test_sum,
                coverage,
                messages,
                total,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            base_id,
            check_id,
            account_id,
            PM,
            n,
            h,
            high_value_sum,
            mus_sum,
            test_sum,
            coverage,
            " | ".join(messages),
            total,
            now
        ])

        # -------------------------
        # 9. Запись результатов
        # -------------------------
        start_id = self.next_id("results")

        rows = []

        for i, (_, row) in enumerate(
                sample_df.iterrows()
        ):
            rows.append((
                start_id + i,
                base_id,
                str(row["doc_id"]),
                str(row["date"]),
                str(row.get("note", "")),
                float(row["amount"]),
                row["selection_type"]
            ))

        self.conn.executemany("""
            INSERT INTO results (
                id,
                base_results_id,
                doc_id,
                date,
                note,
                amount,
                selection_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)

        # -------------------------
        # 10. Возврат
        # -------------------------
        name_acc = self.name

        return {
            "base_id": base_id,
            "name_acc": name_acc,
            "PM": PM,
            "n": n,
            "h": h,
            "total": total,
            "high_value_sum": high_value_sum,
            "mus_sum": mus_sum,
            "test_sum": test_sum,
            "coverage": coverage,
            "messages": messages
        }

    def clear_results(self, account_id: int):

        base_ids = self.conn.execute("""
            SELECT id
            FROM base_results
            WHERE account_id = ?
        """, [account_id]).fetchall()

        base_ids = [row[0] for row in base_ids]

        if not base_ids:
            return

        # DELETE results
        for bid in base_ids:
            self.conn.execute("""
                DELETE FROM results
                WHERE base_results_id = ?
            """, [bid])

        # DELETE base_results
        self.conn.execute("""
            DELETE FROM base_results
            WHERE account_id = ?
        """, [account_id])

    def delete_firm(self, firm_id: int):

        # -------------------------
        # 1. results
        # -------------------------
        self.conn.execute("""
            DELETE FROM results
            WHERE base_results_id IN (
                SELECT id FROM base_results
                WHERE account_id IN (
                    SELECT id FROM accounts
                    WHERE check_id IN (
                        SELECT id FROM checks WHERE firm_id = ?
                    )
                )
            )
        """, [firm_id])

        # -------------------------
        # 2. base_results
        # -------------------------
        self.conn.execute("""
            DELETE FROM base_results
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE check_id IN (
                    SELECT id FROM checks WHERE firm_id = ?
                )
            )
        """, [firm_id])

        # -------------------------
        # 3. entries
        # -------------------------
        self.conn.execute("""
            DELETE FROM entries
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE check_id IN (
                    SELECT id FROM checks WHERE firm_id = ?
                )
            )
        """, [firm_id])

        # -------------------------
        # 4. accounts
        # -------------------------
        self.conn.execute("""
            DELETE FROM accounts
            WHERE check_id IN (
                SELECT id FROM checks WHERE firm_id = ?
            )
        """, [firm_id])

        # -------------------------
        # 5. checks
        # -------------------------
        self.conn.execute("""
            DELETE FROM checks
            WHERE firm_id = ?
        """, [firm_id])

        # -------------------------
        # 6. firms
        # -------------------------
        self.conn.execute("""
            DELETE FROM firms
            WHERE id = ?
        """, [firm_id])

        # -------------------------
        # 7. фиксация
        # -------------------------
        self.conn.commit()


    def delete_checks(self, check_id: int):

        # -------------------------
        # 1. results
        # -------------------------
        self.conn.execute("""
            DELETE FROM results
            WHERE base_results_id IN (
                SELECT id FROM base_results
                WHERE account_id IN (
                    SELECT id FROM accounts
                    WHERE check_id = ?
                )
            )
        """, [check_id])

        # -------------------------
        # 2. base_results
        # -------------------------
        self.conn.execute("""
            DELETE FROM base_results
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE check_id = ?
            )
        """, [check_id])

        # -------------------------
        # 3. entries
        # -------------------------
        self.conn.execute("""
            DELETE FROM entries
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE check_id = ?
            )
        """, [check_id])

        # -------------------------
        # 4. accounts
        # -------------------------
        self.conn.execute("""
            DELETE FROM accounts
            WHERE check_id = ?
        """, [check_id])

        # -------------------------
        # 5. checks
        # -------------------------
        self.conn.execute("""
            DELETE FROM checks
            WHERE id = ?
        """, [check_id])


        # -------------------------
        # 7. фиксация
        # -------------------------
        self.conn.commit()


    def delete_accounts(self, account_id: int):

        # -------------------------
        # 1. results
        # -------------------------
        self.conn.execute("""
            DELETE FROM results
            WHERE base_results_id IN (
                SELECT id FROM base_results
                WHERE account_id IN (
                    SELECT id FROM accounts
                    WHERE id = ?
                )
            )
        """, [account_id])

        # -------------------------
        # 2. base_results
        # -------------------------
        self.conn.execute("""
            DELETE FROM base_results
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE id = ?
            )
        """, [account_id])

        # -------------------------
        # 3. entries
        # -------------------------
        self.conn.execute("""
            DELETE FROM entries
            WHERE account_id IN (
                SELECT id FROM accounts
                WHERE id = ?
            )
        """, [account_id])

        # -------------------------
        # 4. accounts
        # -------------------------
        self.conn.execute("""
            DELETE FROM accounts
            WHERE id = ?
        """, [account_id])


        # -------------------------
        # 7. фиксация
        # -------------------------
        self.conn.commit()

    def delete_acc_desc(self, acc_desc_id: int) -> bool:

        # Проверяем, используется ли этот справочник
        acc_desc = self.conn.execute("""
            SELECT id
            FROM accounts
            WHERE acc_desc_id = ?
            LIMIT 1
        """, [acc_desc_id]).fetchone()

        if acc_desc:
            return False

        # Не используется — можно удалить
        self.conn.execute("""
            DELETE FROM account_desc
            WHERE id = ?
        """, [acc_desc_id])

        self.conn.commit()

        return True
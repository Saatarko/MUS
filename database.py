from typing import Any

import duckdb
import math
import random
from datetime import datetime

import pandas as pd
from PyQt6.QtWidgets import QTableWidgetItem, QPushButton
from sympy import false


class Database:
    def __init__(self, path="audit.db"):
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
            period TEXT,
            materiality DOUBLE,
            created_at TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER,
            check_id INTEGER,
            name TEXT
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
            selection_type TEXT
        )
        """)

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

    # ---------------------------
    # ПОЛУЧЕНИЕ СЫРЫХ ДАННЫХ
    # ---------------------------
    def get_entries(self, account_id: int):
        return self.conn.execute(f"""
        SELECT *
        FROM entries
        WHERE account_id = {account_id}
        ORDER BY amount
        """).df()

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
        return self.conn.execute(f"""
        SELECT 
            e.id,
            e.doc_id,
            e.date,
            e.amount,
            e.note,
            r.selection_type
        FROM results r
        JOIN entries e ON r.entry_id = e.id
        WHERE e.account_id = {account_id}
        ORDER BY e.amount DESC
        """).df()

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

    def get_or_create_account(self, check_id: int, name: str) -> tuple[Any, bool] | tuple[int, bool]:
        existing = self.conn.execute("""
            SELECT id FROM accounts 
            WHERE check_id = ? AND name = ?
        """, [check_id, name]).fetchone()

        if existing:
            return existing[0], False

        new_id = self.next_id("accounts")

        self.conn.execute("""
                    INSERT INTO accounts (id, check_id, name)
                    VALUES (?, ?, ?)
                """, [new_id, check_id, name])

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

    def update_check(self, id: int, period: str, materiality: float) -> int:

        self.conn.execute("""
            UPDATE checks
            SET period = ?, 
                materiality = ?, 
                created_at = ?
            WHERE id = ?
        """, [period, materiality, datetime.now(), id])

        return True

    def update_acc(self, id: int, name: str) -> int:

        self.conn.execute("""
            UPDATE accounts
            SET name = ?
            WHERE id = ?
        """, [name, id])

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
            SELECT id, period, materiality, created_at
            FROM checks
            WHERE firm_id = ?
            ORDER BY created_at DESC
        """, [firm_id]).fetchall()

    def get_one_checks(self, checks_id: int):
        return self.conn.execute("""
            SELECT id, period, materiality, created_at
            FROM checks
            WHERE id = ?
        """,[checks_id]).df()

    def get_accounts(self, check_id: int):
        return self.conn.execute("""
            SELECT id, name
            FROM accounts
            WHERE check_id = ?
            ORDER BY name
        """, [check_id]).fetchall()

    def get_accounts_byid(self, account_id: int):
        return self.conn.execute("""
            SELECT id, name
            FROM accounts
            WHERE id = ?
            ORDER BY name
        """, [account_id]).df()

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

    def add_check(self, firm_id: int, period: str, materiality: float) -> int:
        from datetime import datetime

        new_id = self.next_id("checks")

        self.conn.execute("""
            INSERT INTO checks (id, firm_id, period, materiality, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [new_id, firm_id, period, materiality, datetime.now()])

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

    def run_mus(self, check_id: int, account_id: int):

        messages = []

        # -------------------------
        # 1. PM
        # -------------------------
        pm = self.conn.execute("""
            SELECT materiality
            FROM checks
            WHERE id = ?
        """, [check_id]).fetchone()

        if not pm:
            return {"error": "Check not found"}

        PM = pm[0]

        # -------------------------
        # 3. Entries
        # -------------------------
        df = self.conn.execute("""
            SELECT *
            FROM entries
            WHERE account_id = ?
        """, [account_id]).df()

        if df.empty:
            return {"PM": PM, "n": 0, "h": 0, "messages": ["Нет данных"]}

        df = df.sort_values("amount").reset_index(drop=True)

        total = df["amount"].sum()

        # -------------------------
        # 4. HIGH VALUE
        # -------------------------
        high_value_df = df[df["amount"] >= PM]
        high_value_sum = high_value_df["amount"].sum()

        # исключаем их из MUS
        df_mus = df[df["amount"] < PM].copy()

        # -------------------------
        # 5. FALLBACK
        # -------------------------
        if total <= PM:
            messages.append("⚠ Совокупность < PM → случайная выборка")

            sample_df = df.sample(n=min(5, len(df)))
            sample_df["selection_type"] = "RANDOM"

            n = 0
            h = 0
            mus_sum = sample_df["amount"].sum()

        else:
            # -------------------------
            # 6. MUS
            # -------------------------
            total_mus = df_mus["amount"].sum()

            if total_mus == 0:
                mus_df = pd.DataFrame(columns=df.columns)
                mus_sum = 0
                n = 0
                h = 0
            else:
                n = math.ceil(total_mus / PM)
                h = total_mus / n

                start = random.uniform(0, h)

                df_mus["cum_sum"] = df_mus["amount"].cumsum()

                sample_indices = []
                current_point = start

                while current_point < total_mus:
                    idx = df_mus[df_mus["cum_sum"] >= current_point].index[0]
                    sample_indices.append(idx)
                    current_point += h

                mus_df = df_mus.loc[sample_indices].copy()
                mus_df = mus_df.drop_duplicates(subset=["id"])
                mus_df["selection_type"] = "MUS"

                mus_sum = mus_df["amount"].sum()

            # -------------------------
            # объединяем
            # -------------------------
            high_value_df = high_value_df.copy()
            high_value_df["selection_type"] = "HIGH_VALUE"

            sample_df = pd.concat([high_value_df, mus_df], ignore_index=True)

        # -------------------------
        # 7. Итоги
        # -------------------------
        test_sum = sample_df["amount"].sum()
        coverage = (test_sum / total * 100) if total > 0 else 0

        # -------------------------
        # 8. Очистка старых результатов
        # -------------------------
        self.conn.execute("""
        DELETE FROM base_results
        WHERE check_id = ? AND account_id = ?
        """, [check_id, account_id])

        # -------------------------
        # 9. Запись в БД
        # -------------------------
        now = datetime.now()
        base_id = self.next_id("base_results")

        self.conn.execute("""
        INSERT INTO base_results (
            id,  check_id, account_id,
            PM, n, h,
            high_value_sum, mus_sum, test_sum, coverage,
            messages, total,created_at
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

        start_id = self.next_id("results")

        rows = []
        for i, (_, row) in enumerate(sample_df.iterrows()):
            rows.append((
                start_id + i,
                base_id,
                str(row["doc_id"]),
                str(row["date"]),
                float(row["amount"]),
                row["selection_type"]
            ))

        self.conn.executemany("""
        INSERT INTO results (
            id, base_results_id,
            doc_id, date, amount,
            selection_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, rows)


        name_acc = self.get_accounts_byid(account_id)

        # -------------------------
        # 10. Возврат
        # -------------------------
        return {
            "base_id": base_id,
            "name_acc": name_acc['name'],
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


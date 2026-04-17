import pandas as pd


def pre_parser(file_path: str, sheet_name=0):

    # 1. Читаем файл
    df_raw = pd.read_excel(file_path, header=None, sheet_name=sheet_name)

    # 2. Добавляем колонку с номером строки (с 1)
    df_raw.insert(0, "№ строки", range(1, len(df_raw) + 1))

    return df_raw

def parse_1c_table(
    df_raw: pd.DataFrame,
    id_col: int,
    date_col: int,
    amount_col: int,
    start_row: int,
    end_row: int,
    extra_cols: list = None,
) -> pd.DataFrame:

    # 1. режем данные
    df = df_raw.iloc[start_row:end_row].copy()

    # 2. основные поля
    df["doc_id"] = df[id_col]
    df["date"] = df[date_col]
    df["amount"] = df[amount_col]

    # 3. note
    if extra_cols:
        df["note"] = df[extra_cols].fillna("").astype(str).agg(" ".join, axis=1)
    else:
        df["note"] = ""

    # 4. очистка
    df["doc_id"] = df["doc_id"].astype(str).str.strip()

    df["date"] = df["date"].astype(str).str.strip()

    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
    )

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # 5. фильтрация
    df = df.dropna(subset=["doc_id", "amount", "date"])
    df = df[~df["doc_id"].str.lower().str.contains("итого", na=False)]

    return df[["doc_id", "date", "amount", "note"]].reset_index(drop=True)


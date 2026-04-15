import pandas as pd


def parse_1c_table(
    file_path: str,
    id_col: int,
    date_col: int,
    amount_col: int,
    start_row: int,
    end_row: int,
    extra_cols: list = None,
    sheet_name=0
) -> pd.DataFrame:
    """
    Парсинг таблицы из Excel (1С экспорт) с ручными параметрами.

    Параметры:
    ----------
    file_path : путь к Excel файлу
    id_col : индекс колонки с идентификатором (0-based)
    amount_col : индекс колонки с суммой (0-based)
    date_col: дата
    start_row : начальная строка (0-based, включительно)
    end_row : конечная строка (0-based, включительно)
    extra_cols : список колонок для склейки в примечание
    sheet_name : лист Excel

    Возвращает:
    ----------
    DataFrame с колонками:
        - doc_id
        - amount
        - note
    """
    try:
        id_col -= 1
        date_col -= 1
        amount_col -= 1

        start_row -= 1
        end_row -= 1

        if extra_cols:
            extra_cols = [col - 1 for col in extra_cols]

    except Exception as e:
        print("Внимательно проверьте номера столбцов и ячеек")

    # 1. Читаем весь лист без заголовков
    df_raw = pd.read_excel(file_path, header=None, sheet_name=sheet_name)

    # 2. Обрезаем по заданным границам
    df = df_raw.iloc[start_row:end_row + 1].copy()

    # 3. Вытаскиваем нужные колонки
    df["doc_id"] = df.iloc[:, id_col]
    df["date"] = df.iloc[:, date_col]
    df["amount"] = df.iloc[:, amount_col]

    # 4. Примечание (склейка колонок)
    if extra_cols:
        note_series = []
        for col in extra_cols:
            note_series.append(df.iloc[:, col].astype(str))

        df["note"] = pd.Series(
            [" ".join(vals) for vals in zip(*note_series)],
            index=df.index
        )
    else:
        df["note"] = ""

    # 5. Очистка данных

    # doc_id → строка
    df["doc_id"] = df["doc_id"].astype(str).str.strip()

    # amount → число (очень важно!)
    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
    )

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # 6. Удаляем мусор
    df = df.dropna(subset=["doc_id", "amount", "date"])


    # 7. Убираем строки типа "Итого"
    df = df[~df["doc_id"].str.lower().str.contains("итого", na=False)]

    # 8. Финальный датасет
    df_result = df[["doc_id", "amount", "date", "note"]].reset_index(drop=True)

    return df_result


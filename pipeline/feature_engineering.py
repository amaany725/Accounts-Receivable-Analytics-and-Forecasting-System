def preprocess_new_invoice(company):
    import pandas as pd
    import numpy as np
    import re
    from sqlalchemy import text
    from database import engine
    # =========================
    # LOAD DATA
    # =========================
    historical_df = pd.read_sql(

        f"""
        SELECT *
        FROM historical_invoice
        WHERE company_name = '{company}'
        """,
        engine
    )

    realtime_df = pd.read_sql(

        f"""
        SELECT *
        FROM sales_invoice_raw
        WHERE company_name = '{company}'
        """,
        engine
    )

    realtime_df = realtime_df[
        realtime_df['Status'] == 'Lunas'
    ]

    # =========================================
    # TERM -> ANGKA
    # =========================================
    realtime_df['Term'] = realtime_df['Term'].fillna(0)
    realtime_df['Term'] = realtime_df['Term'].astype(int)

    # =========================================
    # INVOICE AGE
    # =========================================
    realtime_df['invoice_age'] = (
        realtime_df['Due Date'] -
        realtime_df['Transaction Date']
    ).dt.days

    # =========================================
    # CUSTOMER TYPE
    # =========================================
    def kategori_customer(nama):

        if pd.isna(nama):
            return 'UNKNOWN'
        nama = nama.upper()
        if any(x in nama for x in [', PT', ',PT']):
            return 'PT'
        elif any(x in nama for x in [', CV', ',CV']):
            return 'CV'
        elif any(x in nama for x in [', UD', ',UD']):
            return 'UD'
        else:
            return 'PERORANGAN'

    realtime_df['Kategori Customer'] = realtime_df[
        'Customer'
    ].apply(kategori_customer)

    # =========================================
    # KATEGORI ORDER
    # =========================================
    def categorize_order(invoice):

        if pd.isna(invoice):
            return "TRADING"

        invoice = str(invoice).upper()

        match = re.match(r'\d*([A-Z]+)', invoice)

        code = match.group(1) if match else ""

        if code in ["WB", "WN"]:
            return "WORKSHOP"

        elif code in ["CT", "PB", "ZA", "PS", "DX", "LA"]:
            return "TRADING"

        elif "PRO" in invoice:
            return "PROJECT"

        else:
            return "TRADING"

    realtime_df["Kategori Order"] = realtime_df[
        "Invoice Number"
    ].apply(categorize_order)

    # =========================================
    # AMOUNT LOG
    # =========================================
    realtime_df['amount_log'] = np.log1p(
        realtime_df['Total Amount']
    )

    # =========================================
    # AGGREGASI HISTORIS CUSTOMER
    # =========================================
    customer_stats = historical_df.groupby(
        'Customer'
    ).agg({

        'Invoice Number': 'count',
        'Delay': ['mean', 'std', 'last'],
        'Total Amount': 'mean',
        'is_late': 'mean'

    }).reset_index()

    customer_stats.columns = [

        'Customer',
        'customer_freq',
        'avg_delay_customer',
        'delay_std',
        'last_delay',
        'avg_amount_customer',
        'late_ratio'
    ]

    # =========================================
    # MERGE KE REALTIME
    # =========================================
    realtime_df = realtime_df.merge(

        customer_stats,

        on='Customer',

        how='left'
    )

    # =========================================
    # HANDLE CUSTOMER BARU
    # =========================================
    realtime_df['customer_freq'] = (
        realtime_df['customer_freq']
        .fillna(0)
    )

    realtime_df['late_ratio'] = (
        realtime_df['late_ratio']
        .fillna(0)
    )

    # =========================================
    # SORT REALTIME
    # =========================================
    realtime_df = realtime_df.sort_values(
        by=['Customer', 'Transaction Date']
    )

    # =========================================
    # TAMBAHAN COUNT REALTIME
    # =========================================
    realtime_df['realtime_increment'] = (
        realtime_df.groupby('Customer')
        .cumcount()
    )

    # =========================================
    # UPDATE CUSTOMER FREQ
    # =========================================
    realtime_df['customer_freq'] = (
        realtime_df['customer_freq']
        +
        realtime_df['realtime_increment']
        +
        1
    )

    # =========================================
    # UPDATE CUSTOMER REPEAT COUNT
    # =========================================
    realtime_df['customer_repeat_count'] = (
        realtime_df['customer_freq'] - 1
    )

    # =========================================
    # LOYALTY
    # =========================================
    def kategori_loyalty(x):
        if x == 0:
            return 'baru'
        elif x < 3:
            return 'repeat'
        else:
            return 'loyal'
    realtime_df['customer_loyalty'] = (
        realtime_df['customer_repeat_count']
        .apply(kategori_loyalty)
    )

    # =========================================
    # HAPUS KOLOM BANTUAN
    # =========================================
    realtime_df = realtime_df.drop(
        columns=['realtime_increment']
    )

    # =========================================
    # CUSTOMER TYPE OHE
    # BASELINE = CV
    # =========================================
    realtime_df['customer_type_PERORANGAN'] = (
        realtime_df['Kategori Customer'] == 'PERORANGAN'
    )

    realtime_df['customer_type_PT'] = (
        realtime_df['Kategori Customer'] == 'PT'
    )

    realtime_df['customer_type_UD'] = (
        realtime_df['Kategori Customer'] == 'UD'
    )

    # =========================================
    # ORDER TYPE OHE
    # BASELINE = PROJECT
    # =========================================
    realtime_df['Kategori Order_TRADING'] = (
        realtime_df['Kategori Order'] == 'TRADING'
    )
    realtime_df['Kategori Order_WORKSHOP'] = (
        realtime_df['Kategori Order'] == 'WORKSHOP'
    )

    # =========================================
    # IS LATE
    # =========================================
    realtime_df['is_late'] = (
        realtime_df['Delay'] > 0
    ).astype(int)

    # =========================================
    # SAVE KE POSTGRESQL
    # =========================================
    with engine.connect() as conn:
        delete_query = text("""
            DELETE FROM realtime_feature_ready
            WHERE company_name = :company
        """)

        conn.execute(
            delete_query,
            {
                'company': company
            }
        )

        conn.commit()
    realtime_df['company_name'] = company
    realtime_df.to_sql(
        'realtime_feature_ready',
        engine,
        if_exists='append',
        index=False
    )

    print('SAVE TO POSTGRES BERHASIL')
    print('EXPORT EXCEL BERHASIL')
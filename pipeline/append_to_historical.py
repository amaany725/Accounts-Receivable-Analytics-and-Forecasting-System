def append_historical_dataset(company):
    import pandas as pd
    from database import engine

    # =========================================
    # LOAD HISTORICAL
    # =========================================
    historical_df = pd.read_sql(
        f"SELECT * FROM historical_invoice WHERE company_name = '{company}'",
        engine
    )

    # =========================================
    # LOAD REALTIME FEATURE READY
    # =========================================
    realtime_df = pd.read_sql(
        f"SELECT * FROM realtime_feature_ready WHERE company_name = '{company}'",
        engine
    )
    print(f'Total historical: {len(historical_df)}')
    print(f'Total realtime FE: {len(realtime_df)}')

    # =========================================
    # AMBIL TRANSACTION ID HISTORICAL
    # =========================================
    historical_ids = historical_df[
        'Transaction ID'
    ].astype(str)

    # =========================================
    # FILTER YANG BELUM ADA
    # =========================================
    new_data = realtime_df[
        ~realtime_df['Transaction ID']
        .astype(str)
        .isin(historical_ids)
    ]
    new_data = new_data.copy()
    new_data['company_name'] = company
    print(f'Data baru untuk append: {len(new_data)}')

    # =========================================
    # APPEND KE HISTORICAL
    # =========================================
    if len(new_data) > 0:
        # HAPUS KOLOM YANG TIDAK ADA DI HISTORIS
        if 'Current Delay' in new_data.columns:
            new_data = new_data.drop(
                columns=['Current Delay']
            )
        new_data.to_sql(
            'historical_invoice',
            engine,
            if_exists='append',
            index=False
        )
        print('APPEND BERHASIL')
    else:
        print('TIDAK ADA DATA BARU')


import pandas as pd
import requests

from datetime import datetime
from sqlalchemy import text

from database import engine
from pipeline.accurate_utils import (
    clean_term,
    get_valid_access_token
)
# =========================================
# GET SALES INVOICE -> EXPORT EXCEL
# =========================================
def get_invoices(
    company=None,
    sync_mode=None,
    start_date=None,
    end_date=None,
    host=None,
    db_session=None
):

    # host = session.get('db_host')
    # db_session = session.get('db_session')
    access_token = get_valid_access_token()

    if not host:
        return 'Database belum dibuka'

    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-Session-ID': db_session
    }

    hasil = []
    page = 1
    total_pages = 1

    print('AMBIL DATA INVOICE...')

    while page <= total_pages:

        print(f'\nAMBIL PAGE {page}')
        url = (
            f'{host}/accurate/api/sales-invoice/list.do'
            f'?sp.page={page}'
            f'&sp.pageSize=100'
            f'&fields=id,number,customer,status,transDate,dueDate,paymentTerm,totalAmount,paidAmount'
        )

        if start_date and end_date:

            filter_start = datetime.strptime(
                start_date,
                '%Y-%m-%d'
            ).strftime('%d/%m/%Y')

            filter_end = datetime.strptime(
                end_date,
                '%Y-%m-%d'
            ).strftime('%d/%m/%Y')

            url += (
                f'&filter.transDate.op=BETWEEN'
                f'&filter.transDate.val[0]={filter_start}'
                f'&filter.transDate.val[1]={filter_end}'
            )
        response = requests.get(
            url,
            headers=headers,
            timeout = 30
        )
        response_json = response.json()
        data = response_json.get('d', [])

        # =========================
        # AMBIL TOTAL PAGE
        # =========================
        sp = response_json.get('sp', {})
        total_pages = sp.get('pageCount', 1)
        print(response_json.get('sp'))
        print(f'Total invoice page {page}: {len(data)}')
        print(f'Total pages: {total_pages}')

        # =========================
        # LOOP INVOICE
        # =========================
        for inv in data:
            invoice_id = inv.get('id')

            try:
                detail_response = requests.get(
                    f'{host}/accurate/api/sales-invoice/detail.do?id={invoice_id}',
                    headers=headers
                )

                detail = detail_response.json()['d']

                payment_date = detail.get('lastPaymentDate')
                due_date = detail.get('dueDate')

                receipt_history = detail.get(
                    'receiptHistory',
                    []
                )

                payment_method = None

                if receipt_history:
                    payment_method = receipt_history[0].get(
                        'historyPaymentName'
                    )

                total_amount = detail.get(
                    'totalAmount',
                    0
                )

                balance_due = (
                    total_amount
                    if detail.get('statusName') != 'Lunas'
                    else 0
                )

                # =====================================
                # HITUNG DELAY
                # =====================================
                due_date_obj = datetime.strptime(
                    due_date,
                    '%d/%m/%Y'
                ).date()

                today = datetime.today().date()
                delay = 0
                # =====================================
                # SUDAH LUNAS
                # =====================================
                if detail.get('statusName') == 'Lunas':
                    if payment_date:
                        payment_date_obj = datetime.strptime(
                            payment_date,
                            '%d/%m/%Y'
                        ).date()
                        delay = (
                            payment_date_obj - due_date_obj
                        ).days

                # =====================================
                # BELUM LUNAS
                # =====================================
                else:
                    delay = (
                        today - due_date_obj
                    ).days

                hasil.append({
                    'source_system': 'ACCURATE',
                    'company_name': company,
                    'Transaction ID': detail.get('id'),
                    'Invoice Number': detail.get('number'),
                    'Customer': detail.get(
                        'customer',
                        {}
                    ).get('name'),
                    'Status': detail.get('statusName'),
                    'Transaction Date': detail.get('transDate'),
                    'Due Date': due_date,
                    'Term': clean_term(
                        detail.get(
                            'paymentTerm',
                            {}
                        ).get('name')
                    ),
                    'Payment Date': payment_date,
                    'Payment Method': payment_method,
                    'Total Amount': total_amount,
                    'Balance Due': balance_due,
                    'Delay': delay,
                })

                print(
                    f"Berhasil ambil invoice: {detail.get('number')}"
                )
            except Exception as e:
                print(f'ERROR invoice {invoice_id}')
                print(e)

        # =========================
        # NEXT PAGE
        # =========================
        page += 1
    print(f'\nTOTAL FINAL INVOICE: {len(hasil)}')

    # =========================
    # EXPORT EXCEL
    # =========================
    df = pd.DataFrame(hasil)
    df['Transaction Date'] = pd.to_datetime(
        df['Transaction Date'],
        format='%d/%m/%Y',
        errors='coerce'
    )
    df['Due Date'] = pd.to_datetime(
        df['Due Date'],
        format='%d/%m/%Y',
        errors='coerce'
    )
    df['Payment Date'] = pd.to_datetime(
        df['Payment Date'],
        format='%d/%m/%Y',
        errors='coerce'
    )
    numeric_cols = [
        'Total Amount',
        'Balance Due',
        'Delay'
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    conn = engine.connect()
    for _, row in df.iterrows():
        payment_date = row['Payment Date']
        payment_method = row['Payment Method']
        delay = row['Delay']

        # =========================
        # HANDLE NaT / NaN
        # =========================
        if pd.isna(payment_date):
            payment_date = None

        if pd.isna(payment_method):
            payment_method = None

        if pd.isna(delay):
            delay = None

        check_query = text("""
            SELECT COUNT(*)
            FROM sales_invoice_raw
            WHERE source_system = :source_system
            AND company_name = :company_name
            AND "Transaction ID" = :trx_id
        """)

        result = conn.execute(
            check_query,
            {
                "source_system": row['source_system'],
                "trx_id": row['Transaction ID'],
                "company_name": row['company_name']
            }
        )
        exists = result.scalar()

        # ====================================
        # JIKA BELUM ADA -> INSERT
        # ====================================
        if exists == 0:
            insert_query = text("""
                INSERT INTO sales_invoice_raw (
                    company_name,
                    source_system,
                    "Transaction ID",
                    "Invoice Number",
                    "Customer",
                    "Status",
                    "Transaction Date",
                    "Due Date",
                    "Term",
                    "Payment Date",
                    "Payment Method",
                    "Total Amount",
                    "Balance Due",
                    "Delay"
                )
                VALUES (
                    :company_name,
                    :source_system,
                    :transaction_id,
                    :invoice_number,
                    :customer,
                    :status,
                    :transaction_date,
                    :due_date,
                    :term,
                    :payment_date,
                    :payment_method,
                    :total_amount,
                    :balance_due,
                    :delay
                )
            """)

            conn.execute(insert_query, {
                "source_system": row['source_system'],
                "company_name": row['company_name'],
                "transaction_id": row['Transaction ID'],
                "invoice_number": row['Invoice Number'],
                "customer": row['Customer'],
                "status": row['Status'],
                "transaction_date": row['Transaction Date'],
                "due_date": row['Due Date'],
                "term": row['Term'],
                "payment_date": payment_date,
                "payment_method": payment_method,
                "total_amount": row['Total Amount'],
                "balance_due": row['Balance Due'],
                "delay": delay
            })
            print(f"INSERT: {row['Invoice Number']}")

        # ====================================
        # JIKA SUDAH ADA -> UPDATE
        # ====================================
        else:
            update_query = text("""
                UPDATE sales_invoice_raw
                SET
                    "Status" = :status,
                    "Payment Date" = :payment_date,
                    "Payment Method" = :payment_method,
                    "Balance Due" = :balance_due,
                    "Delay" = :delay
                WHERE source_system = :source_system
                AND company_name = :company_name
                AND "Transaction ID" = :transaction_id
            """)

            conn.execute(update_query, {
                "source_system": row['source_system'],
                "transaction_id": row['Transaction ID'],
                "company_name": row['company_name'],
                "status": row['Status'],
                "payment_date": payment_date,
                "payment_method": payment_method,
                "balance_due": row['Balance Due'],
                "delay": delay
            })

            print(f"UPDATE: {row['Invoice Number']}")

    conn.commit()
    conn.close()

    print('DATABASE UPDATED')
    return 'DATABASE UPDATED'


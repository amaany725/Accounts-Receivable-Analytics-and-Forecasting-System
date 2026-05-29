from celery import Celery
import os
from sqlalchemy import text
from database import engine
from pipeline.feature_engineering import preprocess_new_invoice
from pipeline.append_to_historical import append_historical_dataset
from pipeline.invoice_sync import get_invoices

REDIS_URL = os.getenv('REDIS_URL')

celery = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)


@celery.task
def sync_task(
    company,
    sync_mode,
    start_date,
    end_date,
    host,
    db_session,
    access_token
):

    try:

        # =====================================
        # UPDATE STATUS RUNNING
        # =====================================

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE sync_status
                    SET
                        status = 'RUNNING',
                        start_time = NOW(),
                        finish_time = NULL,
                        message = NULL
                    WHERE company_name = :company
                """),
                {
                    "company": company
                }
            )

        print('START BACKGROUND SYNC')

        # =====================================
        # AMBIL DATA INVOICE
        # =====================================

        get_invoices(
            company=company,
            sync_mode=sync_mode,
            start_date=start_date,
            end_date=end_date,
            host=host,
            db_session=db_session,
            access_token=access_token
        )

        print('PREPROCESS FEATURE')

        # =====================================
        # FEATURE ENGINEERING
        # =====================================

        preprocess_new_invoice(company)

        print('APPEND HISTORICAL')

        # =====================================
        # APPEND HISTORICAL
        # =====================================

        append_historical_dataset(company)

        # =====================================
        # UPDATE STATUS SUCCESS
        # =====================================

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE sync_status
                    SET
                        status = 'SUCCESS',
                        finish_time = NOW(),
                        message = 'Sinkronisasi berhasil'
                    WHERE company_name = :company
                """),
                {
                    "company": company
                }
            )

        print('SYNC DONE')

    except Exception as e:

        print('SYNC FAILED')
        print(str(e))

        # =====================================
        # UPDATE STATUS FAILED
        # =====================================

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE sync_status
                    SET
                        status = 'FAILED',
                        finish_time = NOW(),
                        message = :message
                    WHERE company_name = :company
                """),
                {
                    "company": company,
                    "message": str(e)
                }
            )

        raise
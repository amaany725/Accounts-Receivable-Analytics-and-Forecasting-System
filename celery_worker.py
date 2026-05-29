from celery import Celery
import os

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
    db_session
):

    print('START BACKGROUND SYNC')

    get_invoices(
        company=company,
        sync_mode=sync_mode,
        start_date=start_date,
        end_date=end_date,
        host=host,
        db_session=db_session
    )

    print('PREPROCESS FEATURE')

    preprocess_new_invoice(company)

    print('APPEND HISTORICAL')

    append_historical_dataset(company)

    print('SYNC DONE')
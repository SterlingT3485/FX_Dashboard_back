from celery import shared_task
from datetime import datetime, timedelta
import requests
import logging
from .db_utils import DatabaseManager

logger = logging.getLogger(__name__)


@shared_task
def fetch_last_month_data():
    """
    Fetch exchange rate data for the previous month and save to database.
    Scheduled to run on the 1st of each month.
    """
    try:
        # Calculate last month's date range
        today = datetime.now().date()
        first_day_current = today.replace(day=1)
        last_day_last_month = first_day_current - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        
        start_date = first_day_last_month.isoformat()
        end_date = last_day_last_month.isoformat()
        
        logger.info(f"Fetching data for last month: {start_date} to {end_date}")
        
        # Fetch currencies
        currencies_url = "https://api.frankfurter.dev/v1/currencies"
        currencies_response = requests.get(currencies_url, timeout=10)
        currencies_response.raise_for_status()
        currencies_data = currencies_response.json()
        DatabaseManager.save_currencies(currencies_data)
        
        # Fetch exchange rates using CAD as base
        base_currency = 'CAD'
        date_range = f"{start_date}..{end_date}"
        url = f"https://api.frankfurter.dev/v1/{date_range}"
        params = {'base': base_currency}
        
        logger.info(f"Fetching exchange rates for base currency: {base_currency}")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        api_data = response.json()
        
        # Save exchange rates to database
        saved_count = 0
        for date_str, rates_on_date in api_data['rates'].items():
            for target_currency, rate in rates_on_date.items():
                result = DatabaseManager.save_exchange_rate(
                    base_currency,
                    target_currency,
                    rate,
                    date_str
                )
                if result:
                    saved_count += 1
        
        logger.info(f"Successfully saved {saved_count} exchange rate records")
        return {'success': True, 'records_saved': saved_count}
        
    except Exception as e:
        logger.error(f"Error in fetch_last_month_data: {str(e)}")
        raise


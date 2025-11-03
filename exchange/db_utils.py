from django.utils import timezone
from datetime import timedelta
from django.db.models import Min, Max
from .models import ExchangeRate, Currency
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database manager utility class."""
    
    @staticmethod
    def save_exchange_rate(base_currency, target_currency, rate, date, source='frankfurter'):
        """Save exchange rate data to database."""
        try:
            # Check if record already exists
            existing_rate = ExchangeRate.objects.filter(
                base_currency=base_currency,
                target_currency=target_currency,
                date=date
            ).first()
            
            if existing_rate:
                # Update existing record
                existing_rate.rate = rate
                existing_rate.timestamp = timezone.now()
                existing_rate.source = source
                existing_rate.save()
                return existing_rate
            else:
                # Create new record
                exchange_rate = ExchangeRate(
                    base_currency=base_currency,
                    target_currency=target_currency,
                    rate=rate,
                    date=date,
                    source=source
                )
                exchange_rate.save()
                return exchange_rate
                
        except Exception as e:
            logger.error(f"Failed to save exchange rate: {str(e)}")
            return None
    
    @staticmethod
    def save_currencies(currencies_data):
        """Save currency data."""
        try:
            for code, name in currencies_data.items():
                currency, created = Currency.objects.update_or_create(
                    code=code,
                    defaults={'name': name}
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save currencies: {str(e)}")
            return False
    
    @staticmethod
    def database_covers_range(base_currency, target_currencies, request_start, request_end):
        """Return True if DB fully covers [request_start, request_end] for all targets.
        
        If target_currencies is empty, check coverage for the base across any targets.
        """
        if target_currencies:
            for target_currency in target_currencies:
                target_query = ExchangeRate.objects.filter(
                    base_currency=base_currency,
                    target_currency=target_currency
                )
                target_date_range = target_query.aggregate(
                    min_date=Min('date'),
                    max_date=Max('date')
                )
                
                min_date = target_date_range['min_date']
                max_date = target_date_range['max_date']
                if not (min_date and max_date):
                    logger.debug(f"Target {target_currency} has no data in database")
                    return False
                
                if not (min_date <= request_start and max_date >= request_end):
                    logger.debug(
                        f"Target {target_currency} range [{min_date}, {max_date}] doesn't cover request [{request_start}, {request_end}]"
                    )
                    return False
            return True
        
        # No target currencies specified, check for base currency with any target
        base_query = ExchangeRate.objects.filter(base_currency=base_currency)
        db_date_range = base_query.aggregate(min_date=Min('date'), max_date=Max('date'))
        min_date = db_date_range['min_date']
        max_date = db_date_range['max_date']
        return bool(min_date and max_date and (min_date <= request_start) and (max_date >= request_end))
    
    @staticmethod
    def get_time_series_data(base_currency, target_currencies, start_date, end_date):
        """Get time series data from database for the specified date range.
        
        Returns formatted data dict if found, None otherwise.
        """
        try:
            # Check if database covers the range
            from datetime import datetime
            request_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            request_end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else datetime.now().date()
            
            if not DatabaseManager.database_covers_range(base_currency, target_currencies, request_start, request_end):
                logger.debug(f"Database doesn't fully cover request range [{request_start}, {request_end}] for all target currencies")
                return None
            
            # Query the specific data
            query = ExchangeRate.objects.filter(
                base_currency=base_currency,
                date__gte=start_date
            )
            
            if end_date:
                query = query.filter(date__lte=end_date)
            
            if target_currencies:
                query = query.filter(target_currency__in=target_currencies)
            
            # Get data grouped by date
            rates = query.order_by('date')
            
            if not rates.exists():
                return None
            
            # Format data
            db_data = {
                'base': base_currency,
                'start_date': start_date,
                'end_date': end_date if end_date else datetime.now().date().isoformat(),
                'rates': {}
            }
            
            for rate in rates:
                date_str = rate.date.isoformat()
                if date_str not in db_data['rates']:
                    db_data['rates'][date_str] = {}
                db_data['rates'][date_str][rate.target_currency] = float(rate.rate)
            
            return db_data
            
        except Exception as e:
            logger.error(f"Failed to get time series data from database: {str(e)}")
            return None


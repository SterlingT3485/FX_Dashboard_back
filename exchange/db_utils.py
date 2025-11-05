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
    def find_missing_date_ranges(base_currency, target_currency, request_start, request_end):
        """Find missing date ranges for a specific currency pair.
        
        Returns list of (start_date, end_date) tuples for missing ranges.
        """
        # Get existing dates from database
        query = ExchangeRate.objects.filter(
            base_currency=base_currency,
            target_currency=target_currency,
            date__gte=request_start,
            date__lte=request_end
        ).values_list('date', flat=True)
        existing_dates = set(query)
        
        if not existing_dates:
            # No data at all, return the full range
            return [(request_start, request_end)]
        
        missing_ranges = []
        current_date = request_start

        # Find missing ranges
        while current_date <= request_end:
            if current_date not in existing_dates:
                # Found start of missing range
                missing_start = current_date
                # Find end of missing range
                while current_date <= request_end and current_date not in existing_dates:
                    current_date += timedelta(days=1)
                missing_end = current_date - timedelta(days=1)
                missing_ranges.append((missing_start, missing_end))
            else:
                current_date += timedelta(days=1)
        
        return missing_ranges
    
    @staticmethod
    def get_time_series_data(base_currency, target_currencies, start_date, end_date):
        """Get time series data from database for the specified date range.
        
        Returns:
        - If fully covered: data dict
        - If partially covered: tuple (data_dict, missing_ranges_dict)
        - If no data: None
        """
        try:
            from datetime import datetime
            request_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            request_end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else datetime.now().date()
            
            # Query existing data
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
            
            # Check if database fully covers the range
            if DatabaseManager.database_covers_range(base_currency, target_currencies, request_start, request_end):
                # Fully covered, return data dict
                return db_data
            
            # Partially covered, find missing ranges
            missing_ranges = {}
            if target_currencies:
                for target_currency in target_currencies:
                    ranges = DatabaseManager.find_missing_date_ranges(
                        base_currency, target_currency, request_start, request_end
                    )
                    if ranges:
                        missing_ranges[target_currency] = ranges
            else:
                # Get all target that exist for this base
                existing_targets = set(rate.target_currency for rate in rates)
                
                if existing_targets:
                    # Check coverage for each existing target currency
                    for target_currency in existing_targets:
                        ranges = DatabaseManager.find_missing_date_ranges(
                            base_currency, target_currency, request_start, request_end
                        )
                        if ranges:
                            missing_ranges[target_currency] = ranges
            
            # Return tuple if partially covered
            return db_data, missing_ranges
            
        except Exception as e:
            logger.error(f"Failed to get time series data from database: {str(e)}")
            return None

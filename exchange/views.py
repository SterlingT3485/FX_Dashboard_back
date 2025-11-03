# exchange/views.py
from django.http import JsonResponse
from django.views import View
import requests
from datetime import datetime, timedelta
import logging
from django.utils import timezone
from .cache_utils import CacheManager
from .models import ExchangeRate, Currency
from .db_utils import DatabaseManager

logger = logging.getLogger(__name__)

class TimeSeriesView(View):
    """
    get time series data
    """
    
    def get(self, request):
        try:
            # get date range
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date', '')  # empty means latest date
            
            if not start_date:
                return JsonResponse({
                    'success': False,
                    'error': 'start_date parameter is required'
                }, status=400)
            
            # get other parameters
            base_currency = request.GET.get('base', 'EUR')
            symbols = request.GET.get('symbols', '')
            
            # cache key & timeout
            cache_params = {
                'start_date': start_date,
                'end_date': end_date,
                'base': base_currency,
                'symbols': symbols,
            }
            cache_key = CacheManager.generate_cache_key('time_series', cache_params)
            cache_timeout = CacheManager.get_cache_timeout('time_series')

            # 1. Try cache first
            cached = CacheManager.get_cached_data(cache_key, cache_timeout)
            if cached:
                return JsonResponse({
                    'success': True,
                    'data': cached,
                    'source': 'cache'
                })

            # 2. Cache miss, try database
            target_currencies = []
            if symbols:
                target_currencies = [s.strip().upper() for s in symbols.split(',')]
            
            try:
                # Try to get data from database
                db_data = DatabaseManager.get_time_series_data(base_currency, target_currencies, start_date, end_date)
                
                if db_data:
                    CacheManager.set_cached_data(cache_key, db_data, cache_timeout)
                    return JsonResponse({
                        'success': True,
                        'data': db_data,
                        'source': 'database'
                    })
            except Exception as e:
                logger.error(f"Failed to get time series from database: {str(e)}")
            
            # 3. Database doesn't have enough data, call API
            date_range = f"{start_date}..{end_date}" if end_date else f"{start_date}.."
            
            # build API URL
            url = f"https://api.frankfurter.dev/v1/{date_range}"
            params = {}
            
            if base_currency:
                params['base'] = base_currency
            if symbols:
                params['symbols'] = symbols
            
            # call Frankfurter API
            response = requests.get(url, params=params, timeout=15) 
            response.raise_for_status()
            
            api_data = response.json()

            # 4. Save to database
            try:
                for date_str, rates_on_date in api_data['rates'].items():
                    for target_currency, rate in rates_on_date.items():
                        DatabaseManager.save_exchange_rate(
                            api_data['base'],
                            target_currency,
                            rate,
                            date_str
                        )
            except Exception as e:
                logger.error(f"Failed to batch save time series data: {str(e)}")

            # 5. Store to cache
            CacheManager.set_cached_data(cache_key, api_data, cache_timeout)
            
            return JsonResponse({
                'success': True,
                'data': api_data,
                'source': 'frankfurter_api'
            })
            
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'success': False,
                'error': f'API request failed: {str(e)}'
            }, status=500)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=500)


class CurrenciesView(View):
    """
    get supported currencies
    """
    
    def get(self, request):
        try:
            # cache key & timeout
            cache_key = CacheManager.generate_cache_key('currencies', {})
            cache_timeout = CacheManager.get_cache_timeout('currencies')

            # 1. Try cache first
            cached = CacheManager.get_cached_data(cache_key, cache_timeout)
            if cached:
                return JsonResponse({
                    'success': True,
                    'data': cached,
                    'source': 'cache'
                })

            # 2. Cache miss, try database
            try:
                currencies = Currency.objects.all()
                if currencies.exists():
                    db_data = {currency.code: currency.name for currency in currencies}
                    # Update cache
                    CacheManager.set_cached_data(cache_key, db_data, cache_timeout)
                    return JsonResponse({
                        'success': True,
                        'data': db_data,
                        'source': 'database'
                    })
            except Exception as e:
                logger.error(f"Failed to get currencies from database: {str(e)}")

            # 3. Database doesn't have data, call API
            url = "https://api.frankfurter.dev/v1/currencies"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            api_data = response.json()

            # 4. Save to database
            try:
                DatabaseManager.save_currencies(api_data)
            except Exception as e:
                logger.error(f"Failed to save currencies to database: {str(e)}")

            # 5. Store to cache
            CacheManager.set_cached_data(cache_key, api_data, cache_timeout)
            
            return JsonResponse({
                'success': True,
                'data': api_data,
                'source': 'frankfurter_api'
            })
            
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'success': False,
                'error': f'API request failed: {str(e)}'
            }, status=500)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=500)
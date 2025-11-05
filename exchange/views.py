# exchange/views.py
from django.http import JsonResponse
from django.views import View
import requests
from datetime import datetime, timedelta
import logging
from .cache_utils import CacheManager
from .models import ExchangeRate, Currency
from .db_utils import DatabaseManager

logger = logging.getLogger(__name__)

class TimeSeriesView(View):
    """
    get time series data
    """
    
    def _merge_overlapping_ranges(self, ranges):
        """Merge overlapping date ranges.
        
        Returns list of merged (start_date, end_date) tuples.
        """
        if not ranges:
            return []
        
        ranges.sort()
        merged_ranges = []
        current_start, current_end = ranges[0]
        
        for start, end in ranges[1:]:
            if start <= current_end + timedelta(days=1):
                current_end = max(current_end, end)
            else:
                merged_ranges.append((current_start, current_end))
                current_start, current_end = start, end
        merged_ranges.append((current_start, current_end))
        
        return merged_ranges
    
    def _fetch_and_merge_api_data(self, merged_data, base_currency, range_start, range_end, params):
        """Fetch data from API for a date range and merge into merged_data."""
        date_range = f"{range_start.isoformat()}..{range_end.isoformat()}"
        url = f"https://api.frankfurter.dev/v1/{date_range}"
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            api_data = response.json()
            
            # Merge API data into merged_data
            for date_str, rates_on_date in api_data['rates'].items():
                if date_str not in merged_data['rates']:
                    merged_data['rates'][date_str] = {}
                merged_data['rates'][date_str].update(rates_on_date)
                if date_str not in merged_data['_fetched_dates']:
                    merged_data['_fetched_dates'].append(date_str)
            
            return True
        except requests.exceptions.RequestException as e:
            symbol = params.get('symbols', 'all')
            logger.warning(f"Failed to fetch range {date_range} for {symbol}: {str(e)}")
            return False
    
    def _fetch_and_merge_partial_data(self, base_currency, target_currencies, 
                                      partial_data, missing_ranges, 
                                      request_start, request_end):
        """Fetch missing ranges from API and merge with database data."""
        try:
            # Start with partial data from database
            merged_data = {
                'base': partial_data['base'],
                'start_date': partial_data['start_date'],
                'end_date': partial_data['end_date'],
                'rates': partial_data['rates'].copy(),
                '_fetched_dates': []
            }
            
            # Process missing ranges
            if target_currencies:
                # For each target currency, merge its ranges and fetch
                for target_currency, ranges in missing_ranges.items():
                    if not ranges:
                        continue
                    
                    merged_ranges = self._merge_overlapping_ranges(ranges)
                    for range_start, range_end in merged_ranges:
                        params = {
                            'base': base_currency,
                            'symbols': target_currency
                        }
                        self._fetch_and_merge_api_data(merged_data, base_currency, range_start, range_end, params)
            else:
                # No target currencies specified, fetch full request range to get all currencies
                params = {'base': base_currency}
                self._fetch_and_merge_api_data(merged_data, base_currency, request_start, request_end, params)
            
            return merged_data
            
        except Exception as e:
            logger.error(f"Failed to fetch and merge partial data: {str(e)}")
            return None
    
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
            
            # Parse dates
            request_start = datetime.strptime(start_date, '%Y-%m-%d').date()
            request_end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else datetime.now().date()
            
            try:
                # Try to get data from database
                result = DatabaseManager.get_time_series_data(base_currency, target_currencies, start_date, end_date)
                
                if result is None:
                    # No data in database, fetch from API
                    pass
                elif isinstance(result, tuple):
                    # Partially covered: result is (data_dict, missing_ranges_dict)
                    partial_data, missing_ranges = result
                    
                    if partial_data and partial_data.get('rates') and missing_ranges:
                        # Fetch missing ranges from API
                        merged_data = self._fetch_and_merge_partial_data(
                            base_currency, target_currencies, partial_data, 
                            missing_ranges, request_start, request_end
                        )
                        
                        if merged_data:
                            # Save newly fetched data to database
                            try:
                                for date_str, rates_on_date in merged_data['rates'].items():
                                    # Only save dates that were fetched from API
                                    if date_str in merged_data.get('_fetched_dates', []):
                                        for target_currency, rate in rates_on_date.items():
                                            DatabaseManager.save_exchange_rate(
                                                merged_data['base'],
                                                target_currency,
                                                rate,
                                                date_str
                                            )
                            except Exception as e:
                                logger.error(f"Failed to save partial fetch data: {str(e)}")
                            
                            # Remove internal metadata before caching
                            if '_fetched_dates' in merged_data:
                                del merged_data['_fetched_dates']
                            
                            # Store to cache
                            CacheManager.set_cached_data(cache_key, merged_data, cache_timeout)
                            
                            return JsonResponse({
                                'success': True,
                                'data': merged_data,
                                'source': 'partial_fetch'
                            })
                else:
                    # Fully covered: result is data dict
                    db_data = result
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
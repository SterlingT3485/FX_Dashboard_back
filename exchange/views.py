# exchange/views.py
from django.http import JsonResponse
from django.views import View
import requests
from .cache_utils import TTLCacheManager


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
            cache_key = TTLCacheManager.generate_cache_key('time_series', cache_params)
            cache_timeout = TTLCacheManager.get_cache_timeout('time_series')

            # try cache first
            cached = TTLCacheManager.get_cached_data(cache_key, cache_timeout)
            if cached:
                return JsonResponse({
                    'success': True,
                    'data': cached,
                    'source': 'cache'
                })

            # build date range
            date_range = f"{start_date}..{end_date}" if end_date else f"{start_date}.."
            
            # build API URL
            url = f"https://api.frankfurter.dev/v1/{date_range}"
            params = {}
            
            if base_currency and base_currency != 'EUR':
                params['base'] = base_currency
            if symbols:
                params['symbols'] = symbols
            
            # call Frankfurter API
            response = requests.get(url, params=params, timeout=15) 
            response.raise_for_status()
            
            data = response.json()

            # store to cache
            TTLCacheManager.set_cached_data(cache_key, data, cache_timeout)
            
            return JsonResponse({
                'success': True,
                'data': data,
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
            cache_key = TTLCacheManager.generate_cache_key('currencies', {})
            cache_timeout = TTLCacheManager.get_cache_timeout('currencies')

            cached = TTLCacheManager.get_cached_data(cache_key, cache_timeout)
            if cached:
                return JsonResponse({
                    'success': True,
                    'data': cached,
                    'source': 'cache'
                })

            # call Frankfurter API
            url = "https://api.frankfurter.dev/v1/currencies"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()

            # store to cache
            TTLCacheManager.set_cached_data(cache_key, data, cache_timeout)
            
            return JsonResponse({
                'success': True,
                'data': data,
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
# FX Dashboard Backend

Django-based forex exchange rate API service with Redis caching and PostgreSQL database.

## Features

- Time series exchange rate data API
- Currency list API
- Two-layer caching: Redis cache -> PostgreSQL database -> Frankfurter API
- Automatic data persistence to database

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (for PostgreSQL and Redis)
- PostgreSQL 16
- Redis 7

## Setup

### 1. Install Dependencies

```bash
cd FX_Dashboard_back
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Setup

#### Start PostgreSQL Container

```bash
docker run -d --name fx_postgres \
  -e POSTGRES_USER=fxuser \
  -e POSTGRES_PASSWORD=fxpass123 \
  -e POSTGRES_DB=fxdb \
  -p 5432:5432 \
  postgres:16-alpine
```

#### Start Redis Container

```bash
docker run -d --name fx_redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 3. Database Configuration

The database configuration uses environment variables with defaults. Edit `fx_dashboard_back/settings.py` or set environment variables:

```bash
export POSTGRES_DB=fxdb
export POSTGRES_USER=fxuser
export POSTGRES_PASSWORD=fxpass123
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
```

Default configuration in `settings.py`:

- Database: PostgreSQL (fxdb)
- User: fxuser
- Password: fxpass123
- Host: 127.0.0.1
- Port: 5432

### 4. Cache Configuration

Redis cache is configured in `settings.py`:

- Location: `redis://127.0.0.1:6379/0`
- Key prefix: `fx`
- Default timeout: 300 seconds

Cache timeouts (in seconds):

- currencies: 86400 (24 hours) - configured in CACHE_TIMEOUT
- time_series: 1800 (30 minutes) - configured in CACHE_TIMEOUT

### 5. Run Database Migrations

```bash
python manage.py makemigrations exchange
python manage.py migrate
```

## Running the Server

```bash
python manage.py runserver 0.0.0.0:8080
```

The API will be available at:

- `http://127.0.0.1:8080/api/` (localhost)
- `http://localhost:8080/api/` (localhost)

## API Endpoints

### Get Currencies

```
GET /api/currencies/
```

Returns list of supported currencies.

### Get Time Series Data

```
GET /api/timeseries/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&base=CURRENCY&symbols=CURRENCY1,CURRENCY2
```

Parameters:

- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format. If omitted, uses latest available date
- `base` (optional): Base currency code (default: EUR)
- `symbols` (optional): Comma-separated list of target currency codes

Example:

```
GET /api/timeseries/?start_date=2024-10-01&end_date=2024-10-10&base=USD&symbols=EUR,GBP
```

## Data Flow

1. **Cache Layer**: Check Redis cache first
2. **Database Layer**: If cache miss, check PostgreSQL database (only if database date range fully covers request range for all target currencies)
3. **API Layer**: If database doesn't have complete data, call Frankfurter API
4. **Persistence**: Save API responses to database and cache for future requests

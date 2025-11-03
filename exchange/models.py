from django.db import models
from django.utils import timezone


class Currency(models.Model):
    """Supported currencies."""
    code = models.CharField(max_length=3, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'currencies'
        verbose_name_plural = 'currencies'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ExchangeRate(models.Model):
    """Exchange rate data."""
    base_currency = models.CharField(max_length=3)
    target_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    date = models.DateField()  # Rate date
    timestamp = models.DateTimeField(default=timezone.now)  # Data fetch time
    source = models.CharField(max_length=20, default='frankfurter')  # Data source
    
    class Meta:
        db_table = 'exchange_rates'
        indexes = [
            models.Index(fields=['base_currency', 'target_currency', 'date']),
            models.Index(fields=['base_currency', 'date']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-date', '-timestamp']
        unique_together = ['base_currency', 'target_currency', 'date']
    
    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate} ({self.date})"

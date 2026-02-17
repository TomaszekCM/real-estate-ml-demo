from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class ValuationRequest(models.Model):
    """Contains details of a valuation request for a property. Each request will be stored in the database, 
    and linked to a ValuationResult once processed."""

    class Status(models.TextChoices):
        """Status of the valuation request - used to track processing state in the database."""
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        DONE = "DONE"
        FAILED = "FAILED"

    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    area_sqm = models.FloatField(
        validators=[MinValueValidator(10.0), MaxValueValidator(10000.0)],
        help_text="Property area in square meters"
    )
    rooms = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Number of rooms"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ValuationRequest for {self.city}, {self.district} - {self.area_sqm} sqm, {self.rooms} rooms"


class ValuationResult(models.Model):
    """Contains the result of a valuation request. Each result is linked to a ValuationRequest."""
    request = models.OneToOneField(
        ValuationRequest,
        on_delete=models.CASCADE,
        related_name="result"
    )
    estimated_price = models.BigIntegerField(
        help_text="Estimated property price in local currency"
    )
    price_per_sqm = models.IntegerField(
        help_text="Estimated price per square meter"
    )
    model_version = models.CharField(max_length=20, default="v1.0")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"ValuationResult for property {self.request} - Estimated Price: {self.estimated_price}"
    
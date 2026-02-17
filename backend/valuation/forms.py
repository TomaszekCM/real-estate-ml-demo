from django import forms
from .models import ValuationRequest


class ValuationRequestForm(forms.ModelForm):
    """Form for creating property valuation requests"""
    
    class Meta:
        model = ValuationRequest
        fields = ['city', 'district', 'area_sqm', 'rooms']
        
        widgets = {
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter city name (e.g., Warsaw, Krakow)',
                'required': True,
            }),
            'district': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter district (optional)',
            }),
            'area_sqm': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter area in square meters',
                'min': '10',
                'max': '10000',
                'step': '0.1',
                'required': True,
            }),
            'rooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter number of rooms',
                'min': '1',
                'max': '20',
                'required': True,
            }),
        }
        
        labels = {
            'city': 'City',
            'district': 'District',
            'area_sqm': 'Area (m²)',
            'rooms': 'Number of Rooms',
        }
        
        help_texts = {
            'area_sqm': 'Property area in square meters (10-10,000)',
            'rooms': 'Total number of rooms (1-20)',
            'district': 'Optional - district or neighborhood name',
        }
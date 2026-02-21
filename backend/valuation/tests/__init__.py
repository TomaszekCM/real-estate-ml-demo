"""
Test package for valuation app
Organized test modules for better maintainability
"""

# Import all test classes so they're discoverable by Django's test runner
from .test_infrastructure import *
from .test_models import *  
from .test_views import *
from .test_tasks import *
from .test_integration import *
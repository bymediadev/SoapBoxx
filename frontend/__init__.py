# frontend/__init__.py
# This file makes the frontend directory a Python package

from .main_window import MainWindow
from .soapboxx_tab import SoapBoxxTab
from .reverb_tab import ReverbTab
from .scoop_tab import ScoopTab

__all__ = [
    'MainWindow',
    'SoapBoxxTab',
    'ReverbTab', 
    'ScoopTab'
]

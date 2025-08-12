# frontend/__init__.py
# This file makes the frontend directory a Python package

from .main_window import MainWindow
from .reverb_tab import ReverbTab
from .scoop_tab import ScoopTab
from .soapboxx_tab import SoapBoxxTab

__all__ = ["MainWindow", "SoapBoxxTab", "ReverbTab", "ScoopTab"]

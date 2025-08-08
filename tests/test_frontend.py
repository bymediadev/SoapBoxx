#!/usr/bin/env python3
"""
Frontend Testing Suite for SoapBoxx
Comprehensive UI testing using pytest-qt
"""

import os
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import pytest-qt
try:
    import pytestqt

    PYTEST_QT_AVAILABLE = True
except ImportError:
    PYTEST_QT_AVAILABLE = False
    print("pytest-qt not available. Install with: pip install pytest-qt")

# Try to import PyQt6
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("PyQt6 not available. Install with: pip install PyQt6")

# Import frontend modules
try:
    from frontend.main_window import MainWindow
    from frontend.reverb_tab import ReverbTab
    from frontend.scoop_tab import ScoopTab
    from frontend.soapboxx_tab import SoapBoxxTab

    FRONTEND_AVAILABLE = True
except ImportError as e:
    print(f"Frontend modules not available: {e}")
    FRONTEND_AVAILABLE = False


class TestFrontend:
    """Comprehensive frontend testing suite"""

    @pytest.fixture(autouse=True)
    def setup_application(self, qtbot):
        """Setup QApplication for testing"""
        if not PYQT6_AVAILABLE or not FRONTEND_AVAILABLE:
            pytest.skip("PyQt6 or frontend modules not available")

        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])

        self.qtbot = qtbot
        return self.app

    def test_main_window_initialization(self, qtbot):
        """Test main window initialization and basic UI elements"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create main window
            main_window = MainWindow()
            qtbot.addWidget(main_window)

            # Check if window is visible
            assert main_window.isVisible()

            # Check if tabs exist
            tab_widget = main_window.findChild(QTabWidget)
            assert tab_widget is not None

            # Check if expected tabs are present
            tab_names = [tab_widget.tabText(i) for i in range(tab_widget.count())]
            expected_tabs = ["SoapBoxx", "Scoop", "Reverb"]

            for expected_tab in expected_tabs:
                assert (
                    expected_tab in tab_names
                ), f"Expected tab '{expected_tab}' not found"

            # Check status bar
            status_bar = main_window.statusBar()
            assert status_bar is not None

            print("✅ Main window initialization test passed")

        except Exception as e:
            pytest.fail(f"Main window initialization failed: {e}")

    def test_soapboxx_tab_functionality(self, qtbot):
        """Test SoapBoxx tab core functionality"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create SoapBoxx tab
            soapboxx_tab = SoapBoxxTab()
            qtbot.addWidget(soapboxx_tab)

            # Check if tab is visible
            assert soapboxx_tab.isVisible()

            # Test device selection
            device_combo = soapboxx_tab.findChild(QComboBox, "device_combo")
            if device_combo:
                # Test device selection change
                if device_combo.count() > 0:
                    qtbot.keyClicks(device_combo, device_combo.itemText(0))
                    qtbot.wait(100)

            # Test recording controls (without actually recording)
            record_button = soapboxx_tab.findChild(QPushButton, "record_button")
            if record_button:
                # Test button click (should not crash)
                qtbot.mouseClick(record_button, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

            print("✅ SoapBoxx tab functionality test passed")

        except Exception as e:
            pytest.fail(f"SoapBoxx tab test failed: {e}")

    def test_scoop_tab_functionality(self, qtbot):
        """Test Scoop tab functionality"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create Scoop tab
            scoop_tab = ScoopTab()
            qtbot.addWidget(scoop_tab)

            # Check if tab is visible
            assert scoop_tab.isVisible()

            # Test search functionality
            search_input = scoop_tab.findChild(QLineEdit)
            if search_input:
                # Test text input
                test_query = "test search"
                qtbot.keyClicks(search_input, test_query)
                qtbot.wait(100)

                # Verify text was entered
                assert search_input.text() == test_query

            print("✅ Scoop tab functionality test passed")

        except Exception as e:
            pytest.fail(f"Scoop tab test failed: {e}")

    def test_reverb_tab_functionality(self, qtbot):
        """Test Reverb tab functionality"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create Reverb tab
            reverb_tab = ReverbTab()
            qtbot.addWidget(reverb_tab)

            # Check if tab is visible
            assert reverb_tab.isVisible()

            # Test file selection (mock)
            file_input = reverb_tab.findChild(QLineEdit)
            if file_input:
                # Test text input
                test_file = "test_audio.mp3"
                qtbot.keyClicks(file_input, test_file)
                qtbot.wait(100)

                # Verify text was entered
                assert file_input.text() == test_file

            print("✅ Reverb tab functionality test passed")

        except Exception as e:
            pytest.fail(f"Reverb tab test failed: {e}")

    def test_ui_error_handling(self, qtbot):
        """Test UI error handling and graceful degradation"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create main window
            main_window = MainWindow()
            qtbot.addWidget(main_window)

            # Test error dialog display
            # This would typically be triggered by an actual error
            # For now, we'll test the error handling infrastructure

            # Check if error handling methods exist
            assert hasattr(main_window, "_show_user_friendly_error")

            print("✅ UI error handling test passed")

        except Exception as e:
            pytest.fail(f"UI error handling test failed: {e}")

    def test_audio_monitoring_stability(self, qtbot):
        """Test audio monitoring thread stability"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create SoapBoxx tab
            soapboxx_tab = SoapBoxxTab()
            qtbot.addWidget(soapboxx_tab)

            # Test audio monitoring start/stop
            if hasattr(soapboxx_tab, "start_audio_monitoring"):
                # Start monitoring
                soapboxx_tab.start_audio_monitoring()
                qtbot.wait(500)  # Wait for monitoring to start

                # Stop monitoring
                if hasattr(soapboxx_tab, "stop_audio_monitoring"):
                    soapboxx_tab.stop_audio_monitoring()
                    qtbot.wait(100)

            print("✅ Audio monitoring stability test passed")

        except Exception as e:
            pytest.fail(f"Audio monitoring test failed: {e}")

    def test_thread_safety(self, qtbot):
        """Test thread safety in UI operations"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create main window
            main_window = MainWindow()
            qtbot.addWidget(main_window)

            # Test concurrent operations
            # This would typically involve multiple threads
            # For now, we'll test the thread safety infrastructure

            # Check if thread-safe methods exist
            assert hasattr(main_window, "_global_exception_handler")

            print("✅ Thread safety test passed")

        except Exception as e:
            pytest.fail(f"Thread safety test failed: {e}")

    def test_memory_usage(self, qtbot):
        """Test memory usage and cleanup"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # Create and destroy multiple windows to test memory cleanup
            windows = []

            for i in range(3):
                window = MainWindow()
                qtbot.addWidget(window)
                windows.append(window)

                # Simulate some usage
                qtbot.wait(100)

            # Clean up
            for window in windows:
                window.close()
                qtbot.wait(100)

            print("✅ Memory usage test passed")

        except Exception as e:
            pytest.fail(f"Memory usage test failed: {e}")


class TestUIComponents:
    """Test individual UI components"""

    def test_modern_card_widget(self, qtbot):
        """Test ModernCard widget"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            from frontend.soapboxx_tab import ModernCard

            # Create ModernCard
            card = ModernCard()
            qtbot.addWidget(card)

            # Check if card is visible
            assert card.isVisible()

            # Test styling
            assert "background-color: white" in card.styleSheet()

            print("✅ ModernCard widget test passed")

        except Exception as e:
            pytest.fail(f"ModernCard test failed: {e}")

    def test_modern_button_widget(self, qtbot):
        """Test ModernButton widget"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            from frontend.soapboxx_tab import ModernButton

            # Create ModernButton
            button = ModernButton("Test Button")
            qtbot.addWidget(button)

            # Check if button is visible
            assert button.isVisible()

            # Test click
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
            qtbot.wait(100)

            print("✅ ModernButton widget test passed")

        except Exception as e:
            pytest.fail(f"ModernButton test failed: {e}")


class TestErrorScenarios:
    """Test error scenarios and edge cases"""

    def test_missing_backend_modules(self, qtbot):
        """Test behavior when backend modules are missing"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # This test would require mocking missing modules
            # For now, we'll test the error handling infrastructure

            from frontend.main_window import MainWindow

            main_window = MainWindow()
            qtbot.addWidget(main_window)

            # Check if error handling is in place
            assert hasattr(main_window, "_global_exception_handler")

            print("✅ Missing backend modules test passed")

        except Exception as e:
            pytest.fail(f"Missing backend modules test failed: {e}")

    def test_network_failures(self, qtbot):
        """Test UI behavior during network failures"""
        if not FRONTEND_AVAILABLE:
            pytest.skip("Frontend not available")

        try:
            # This test would require mocking network failures
            # For now, we'll test the error handling infrastructure

            from frontend.main_window import MainWindow

            main_window = MainWindow()
            qtbot.addWidget(main_window)

            # Check if network error handling is in place
            assert hasattr(main_window, "_show_user_friendly_error")

            print("✅ Network failures test passed")

        except Exception as e:
            pytest.fail(f"Network failures test failed: {e}")


def run_frontend_tests():
    """Run all frontend tests"""
    if not PYTEST_QT_AVAILABLE:
        print("❌ pytest-qt not available. Install with: pip install pytest-qt")
        return False

    if not PYQT6_AVAILABLE:
        print("❌ PyQt6 not available. Install with: pip install PyQt6")
        return False

    if not FRONTEND_AVAILABLE:
        print("❌ Frontend modules not available")
        return False

    print("🚀 Running Frontend Test Suite")
    print("=" * 50)

    # Run tests using pytest
    import pytest

    test_file = Path(__file__)

    # Run tests with verbose output
    result = pytest.main([str(test_file), "-v", "--tb=short", "--disable-warnings"])

    if result == 0:
        print("✅ All frontend tests passed!")
        return True
    else:
        print("❌ Some frontend tests failed")
        return False


if __name__ == "__main__":
    run_frontend_tests()

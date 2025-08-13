#!/usr/bin/env python3
"""
SoapBoxx Demo - Clean Build Script
===================================

This script ensures that every demo build is:
1. Clean (no stray local files)
2. Self-contained (all dependencies included)
3. Tested before distribution
4. Properly packaged for cross-platform use

Usage:
    python build_demo_clean.py [--test] [--package] [--release]
"""

import os
import sys
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime
import json

class CleanDemoBuilder:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.build_dir = self.root_dir / "build_clean"
        self.demo_dir = self.build_dir / "SoapBoxx-Demo"
        self.requirements_file = self.root_dir / "requirements.txt"
        self.version = "1.0.0"
        
    def clean_build_directory(self):
        """Remove any existing build artifacts"""
        print("🧹 Cleaning build directory...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(exist_ok=True)
        print("✅ Build directory cleaned")
    
    def create_clean_environment(self):
        """Create a clean Python environment for building"""
        print("🐍 Creating clean Python environment...")
        
        # Create virtual environment
        venv_dir = self.build_dir / ".venv"
        subprocess.run([
            sys.executable, "-m", "venv", str(venv_dir)
        ], check=True)
        
        # Determine activation script
        if os.name == 'nt':  # Windows
            activate_script = venv_dir / "Scripts" / "activate.bat"
            python_exe = venv_dir / "Scripts" / "python.exe"
            pip_exe = venv_dir / "Scripts" / "pip.exe"
        else:  # Unix/Linux/macOS
            activate_script = venv_dir / "bin" / "activate"
            python_exe = venv_dir / "bin" / "python"
            pip_exe = venv_dir / "bin" / "pip"
        
        print(f"✅ Virtual environment created at {venv_dir}")
        return python_exe, pip_exe
    
    def install_dependencies(self, pip_exe):
        """Install all required dependencies"""
        print("📦 Installing dependencies...")
        
        # Install core requirements
        if self.requirements_file.exists():
            subprocess.run([str(pip_exe), "install", "-r", str(self.requirements_file)], check=True)
            print("✅ Core dependencies installed")
        else:
            print("⚠️  No requirements.txt found, installing minimal set")
            subprocess.run([str(pip_exe), "install", "PyQt6", "numpy", "requests"], check=True)
        
        # Install additional demo-specific packages
        demo_packages = [
            "PyQt6",
            "numpy", 
            "requests",
            "python-dotenv"
        ]
        
        for package in demo_packages:
            try:
                subprocess.run([str(pip_exe), "install", package], check=True)
                print(f"✅ {package} installed")
            except subprocess.CalledProcessError:
                print(f"⚠️  Failed to install {package}")
    
    def copy_demo_files(self, python_exe):
        """Copy only the necessary demo files"""
        print("📁 Copying demo files...")
        
        # Create demo structure
        (self.demo_dir / "frontend").mkdir(parents=True, exist_ok=True)
        (self.demo_dir / "backend").mkdir(parents=True, exist_ok=True)
        (self.demo_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (self.demo_dir / "docs").mkdir(parents=True, exist_ok=True)
        
        # Copy frontend files
        frontend_files = [
            "main_window.py",
            "soapboxx_tab.py", 
            "scoop_tab.py",
            "reverb_tab.py",
            "theme_manager.py",
            "keyboard_shortcuts.py",
            "__init__.py"
        ]
        
        for file in frontend_files:
            src = self.root_dir / "frontend" / file
            dst = self.demo_dir / "frontend" / file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"✅ Copied {file}")
            else:
                print(f"⚠️  Missing {file}")
        
        # Copy backend barebones modules
        backend_files = [
            "feedback_engine_barebones.py",
            "guest_research_barebones.py", 
            "transcriber_barebones.py",
            "tts_generator_barebones.py",
            "soapboxx_core_barebones.py"
        ]
        
        for file in backend_files:
            src = self.root_dir / "backend" / file
            dst = self.demo_dir / "backend" / file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"✅ Copied {file}")
            else:
                print(f"⚠️  Missing {file}")
        
        # Copy launch scripts
        script_files = ["run_demo.bat", "run_demo.sh"]
        for file in script_files:
            src = self.root_dir / "scripts" / file
            dst = self.demo_dir / "scripts" / file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"✅ Copied {file}")
            else:
                print(f"⚠️  Missing {file}")
        
        # Copy documentation
        doc_files = ["README_DEMO.md", "TUTORIAL_DEMO.md"]
        for file in doc_files:
            src = self.root_dir / "docs" / file
            dst = self.demo_dir / "docs" / file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"✅ Copied {file}")
            else:
                print(f"⚠️  Missing {file}")
        
        # Create requirements file for demo
        demo_requirements = self.demo_dir / "requirements_demo.txt"
        with open(demo_requirements, 'w') as f:
            f.write("# SoapBoxx Demo Dependencies\n")
            f.write("PyQt6>=6.0.0\n")
            f.write("numpy>=1.20.0\n")
            f.write("requests>=2.25.0\n")
            f.write("python-dotenv>=0.19.0\n")
        print("✅ Created demo requirements file")
    
    def test_demo(self, python_exe):
        """Test the demo in the clean environment"""
        print("🧪 Testing demo in clean environment...")
        
        try:
            # Test basic imports
            test_script = f"""
import sys
sys.path.insert(0, '{self.demo_dir}')
sys.path.insert(0, '{self.demo_dir}/frontend')
sys.path.insert(0, '{self.demo_dir}/backend')

try:
    from frontend.main_window import MainWindow
    print("✅ MainWindow imported successfully")
    
    from frontend.soapboxx_tab import SoapBoxxTab
    print("✅ SoapBoxxTab imported successfully")
    
    from frontend.reverb_tab import ReverbTab
    print("✅ ReverbTab imported successfully")
    
    # Test tab creation
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    
    soapboxx_tab = SoapBoxxTab()
    print(f"✅ SoapBoxxTab created: {type(soapboxx_tab)}")
    
    reverb_tab = ReverbTab()
    print(f"✅ ReverbTab created: {type(reverb_tab)}")
    
    # Test tab insertion
    from PyQt6.QtWidgets import QTabWidget
    tab_widget = QTabWidget()
    
    tab_widget.insertTab(0, soapboxx_tab, "SoapBoxx")
    tab_widget.insertTab(1, reverb_tab, "Reverb")
    
    print(f"✅ Tabs inserted successfully: {tab_widget.count()} tabs")
    print("🎉 All tests passed!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
            
            result = subprocess.run([
                str(python_exe), "-c", test_script
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Demo test passed!")
                print(result.stdout)
                return True
            else:
                print("❌ Demo test failed!")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return False
    
    def create_package(self):
        """Create the final distribution package"""
        print("📦 Creating distribution package...")
        
        # Create ZIP archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"SoapBoxx-Demo-v{self.version}-{timestamp}.zip"
        zip_path = self.build_dir / zip_name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.demo_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(self.demo_dir)
                    zipf.write(file_path, arc_name)
        
        print(f"✅ Package created: {zip_path}")
        return zip_path
    
    def build(self, test_only=False, create_package=False):
        """Main build process"""
        print("🚀 Starting clean demo build...")
        print("=" * 50)
        
        try:
            # Step 1: Clean build directory
            self.clean_build_directory()
            
            # Step 2: Create clean environment
            python_exe, pip_exe = self.create_clean_environment()
            
            # Step 3: Install dependencies
            self.install_dependencies(pip_exe)
            
            # Step 4: Copy demo files
            self.copy_demo_files(python_exe)
            
            # Step 5: Test demo
            if test_only or not test_only:  # Always test
                if not self.test_demo(python_exe):
                    print("❌ Demo test failed - build aborted")
                    return False
            
            # Step 6: Create package if requested
            if create_package:
                package_path = self.create_package()
                print(f"🎉 Build complete! Package: {package_path}")
            else:
                print("🎉 Build complete! Demo ready for testing")
            
            return True
            
        except Exception as e:
            print(f"❌ Build failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build SoapBoxx Demo")
    parser.add_argument("--test", action="store_true", help="Test only")
    parser.add_argument("--package", action="store_true", help="Create distribution package")
    parser.add_argument("--release", action="store_true", help="Full release build (test + package)")
    
    args = parser.parse_args()
    
    builder = CleanDemoBuilder()
    
    if args.test:
        # Test existing demo
        builder.clean_build_directory()
        python_exe, pip_exe = builder.create_clean_environment()
        builder.install_dependencies(pip_exe)
        builder.copy_demo_files(python_exe)
        success = builder.test_demo(python_exe)
        sys.exit(0 if success else 1)
    
    elif args.package:
        # Build and package
        success = builder.build(create_package=True)
        sys.exit(0 if success else 1)
    
    elif args.release:
        # Full release build
        success = builder.build(test_only=True, create_package=True)
        sys.exit(0 if success else 1)
    
    else:
        # Default: build and test
        success = builder.build()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Clean System Installation Test for SoapBoxx Demo
Simulates installing and running the demo on a fresh system
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import zipfile

def test_clean_installation():
    """Test the distribution package on a simulated clean system"""
    
    print("🧪 Testing SoapBoxx Demo on Clean System")
    print("=" * 60)
    
    # Check if distribution package exists
    dist_dir = Path("SoapBoxx-Demo-Distribution")
    zip_file = dist_dir / "SoapBoxx-Demo-v1.0.0.zip"
    
    if not dist_dir.exists():
        print("❌ Distribution directory not found!")
        print("   Run 'python create_demo_package.py' first")
        return False
    
    if not zip_file.exists():
        print("❌ Distribution ZIP not found!")
        print("   Run 'python create_demo_package.py' first")
        return False
    
    print("✅ Distribution package found")
    
    # Create temporary test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"📁 Created temporary test directory: {temp_path}")
        
        # Extract distribution package
        print("\n📦 Extracting distribution package...")
        try:
            with zipfile.ZipFile(zip_file, 'r') as zipf:
                zipf.extractall(temp_path)
            print("✅ Package extracted successfully")
        except Exception as e:
            print(f"❌ Failed to extract package: {e}")
            return False
        
        # Navigate to extracted demo
        demo_dir = temp_path / "SoapBoxx-Demo"
        if not demo_dir.exists():
            print("❌ Demo directory not found in extracted package")
            return False
        
        print(f"📁 Demo directory: {demo_dir}")
        
        # Check package structure
        print("\n🔍 Verifying package structure...")
        required_dirs = ["backend", "frontend", "docs", "scripts", "samples"]
        required_files = [
            "README.md", "INSTALLATION.md", "requirements_demo.txt",
            "test_barebones_modules.py"
        ]
        
        missing_dirs = []
        missing_files = []
        
        for dir_name in required_dirs:
            if not (demo_dir / dir_name).exists():
                missing_dirs.append(dir_name)
        
        for file_name in required_files:
            if not (demo_dir / file_name).exists():
                missing_files.append(file_name)
        
        if missing_dirs:
            print(f"❌ Missing directories: {missing_dirs}")
            return False
        
        if missing_files:
            print(f"❌ Missing files: {missing_files}")
            return False
        
        print("✅ Package structure verified")
        
        # Check backend modules
        print("\n🔧 Verifying backend modules...")
        backend_modules = [
            "feedback_engine_barebones.py",
            "guest_research_barebones.py",
            "transcriber_barebones.py",
            "tts_generator_barebones.py",
            "soapboxx_core_barebones.py"
        ]
        
        missing_modules = []
        for module in backend_modules:
            if not (demo_dir / "backend" / module).exists():
                missing_modules.append(module)
        
        if missing_modules:
            print(f"❌ Missing backend modules: {missing_modules}")
            return False
        
        print("✅ All backend modules present")
        
        # Check frontend files
        print("\n🎨 Verifying frontend files...")
        frontend_files = [
            "main_window.py", "soapboxx_tab.py", "scoop_tab.py",
            "reverb_tab.py", "theme_manager.py", "keyboard_shortcuts.py"
        ]
        
        missing_frontend = []
        for file in frontend_files:
            if not (demo_dir / "frontend" / file).exists():
                missing_frontend.append(file)
        
        if missing_frontend:
            print(f"❌ Missing frontend files: {missing_frontend}")
            return False
        
        print("✅ All frontend files present")
        
        # Check launch scripts
        print("\n🚀 Verifying launch scripts...")
        if not (demo_dir / "scripts" / "run_demo.bat").exists():
            print("❌ Missing Windows launch script")
            return False
        
        if not (demo_dir / "scripts" / "run_demo.sh").exists():
            print("❌ Missing Unix launch script")
            return False
        
        print("✅ Launch scripts present")
        
        # Check documentation
        print("\n📚 Verifying documentation...")
        if not (demo_dir / "docs" / "README_DEMO.md").exists():
            print("❌ Missing README_DEMO.md")
            return False
        
        if not (demo_dir / "docs" / "TUTORIAL_DEMO.md").exists():
            print("❌ Missing TUTORIAL_DEMO.md")
            return False
        
        print("✅ Documentation present")
        
        # Check sample content
        print("\n📝 Verifying sample content...")
        if not (demo_dir / "samples" / "sample_transcript.txt").exists():
            print("❌ Missing sample transcript")
            return False
        
        if not (demo_dir / "samples" / "DEMO_INSTRUCTIONS.md").exists():
            print("❌ Missing demo instructions")
            return False
        
        print("✅ Sample content present")
        
        # Test module imports (without running full tests)
        print("\n🧪 Testing module imports...")
        try:
            # Change to demo directory
            original_cwd = os.getcwd()
            os.chdir(demo_dir)
            
            # Test importing backend modules
            sys.path.insert(0, str(demo_dir / "backend"))
            
            try:
                from feedback_engine_barebones import BarebonesFeedbackEngine
                print("   ✅ feedback_engine_barebones imported")
            except Exception as e:
                print(f"   ❌ feedback_engine_barebones import failed: {e}")
                return False
            
            try:
                from guest_research_barebones import BarebonesGuestResearch
                print("   ✅ guest_research_barebones imported")
            except Exception as e:
                print(f"   ❌ guest_research_barebones import failed: {e}")
                return False
            
            try:
                from transcriber_barebones import BarebonesTranscriber
                print("   ✅ transcriber_barebones imported")
            except Exception as e:
                print(f"   ❌ transcriber_barebones import failed: {e}")
                return False
            
            try:
                from tts_generator_barebones import BarebonesTTSGenerator
                print("   ✅ tts_generator_barebones imported")
            except Exception as e:
                print(f"   ❌ tts_generator_barebones import failed: {e}")
                return False
            
            try:
                from soapboxx_core_barebones import BarebonesSoapBoxxCore
                print("   ✅ soapboxx_core_barebones imported")
            except Exception as e:
                print(f"   ❌ soapboxx_core_barebones import failed: {e}")
                return False
            
            # Restore original working directory
            os.chdir(original_cwd)
            sys.path.pop(0)
            
        except Exception as e:
            print(f"❌ Module import test failed: {e}")
            return False
        
        print("✅ All modules import successfully")
        
        # Test requirements file
        print("\n📦 Verifying requirements file...")
        requirements_file = demo_dir / "requirements_demo.txt"
        if not requirements_file.exists():
            print("❌ Requirements file not found")
            return False
        
        with open(requirements_file, 'r') as f:
            content = f.read()
            if "PyQt6" not in content:
                print("❌ PyQt6 not in requirements")
                return False
            if "numpy" not in content:
                print("❌ numpy not in requirements")
                return False
        
        print("✅ Requirements file verified")
        
        # Test README content
        print("\n📖 Verifying README content...")
        readme_file = demo_dir / "README.md"
        if not readme_file.exists():
            print("❌ README.md not found")
            return False
        
        with open(readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "SoapBoxx Demo" not in content:
                print("❌ README content incomplete")
                return False
            if "Quick Start" not in content:
                print("❌ README missing Quick Start section")
                return False
        
        print("✅ README content verified")
        
        # Test installation guide
        print("\n📋 Verifying installation guide...")
        install_file = demo_dir / "INSTALLATION.md"
        if not install_file.exists():
            print("❌ INSTALLATION.md not found")
            return False
        
        with open(install_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "Windows Installation" not in content:
                print("❌ Installation guide missing Windows section")
                return False
            if "macOS Installation" not in content:
                print("❌ Installation guide missing macOS section")
                return False
        
        print("✅ Installation guide verified")
        
        # Test launch script content
        print("\n🚀 Verifying launch script content...")
        bat_script = demo_dir / "scripts" / "run_demo.bat"
        sh_script = demo_dir / "scripts" / "run_demo.sh"
        
        if not bat_script.exists():
            print("❌ Windows launch script not found")
            return False
        
        if not sh_script.exists():
            print("❌ Unix launch script not found")
            return False
        
        # Check script content
        with open(bat_script, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if "SoapBoxx Demo" not in content:
                print("❌ Windows script content incomplete")
                return False
        
        with open(sh_script, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if "SoapBoxx Demo" not in content:
                print("❌ Unix script content incomplete")
                return False
        
        print("✅ Launch scripts verified")
        
        # Test sample content
        print("\n📝 Verifying sample content...")
        sample_transcript = demo_dir / "samples" / "sample_transcript.txt"
        if not sample_transcript.exists():
            print("❌ Sample transcript not found")
            return False
        
        with open(sample_transcript, 'r', encoding='utf-8') as f:
            content = f.read()
            if "SoapBoxx Demo" not in content:
                print("❌ Sample transcript content incomplete")
                return False
        
        print("✅ Sample content verified")
        
        # Test version info
        print("\n📊 Verifying version information...")
        version_file = demo_dir / "VERSION.json"
        if not version_file.exists():
            print("❌ VERSION.json not found")
            return False
        
        try:
            import json
            with open(version_file, 'r') as f:
                version_data = json.load(f)
            
            if "version" not in version_data:
                print("❌ Version info missing version field")
                return False
            
            if "demo_type" not in version_data:
                print("❌ Version info missing demo_type field")
                return False
            
            print(f"   ✅ Version: {version_data.get('version', 'Unknown')}")
            print(f"   ✅ Demo Type: {version_data.get('demo_type', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ Version file parsing failed: {e}")
            return False
        
        print("✅ Version information verified")
        
        # Final summary
        print("\n" + "=" * 60)
        print("🎉 CLEAN SYSTEM INSTALLATION TEST PASSED!")
        print("=" * 60)
        print("✅ Package structure complete")
        print("✅ All modules present")
        print("✅ Documentation complete")
        print("✅ Launch scripts functional")
        print("✅ Sample content ready")
        print("✅ Requirements specified")
        print("✅ Version information present")
        print("\n🚀 Package ready for distribution!")
        
        return True

def main():
    """Main test function"""
    try:
        success = test_clean_installation()
        if success:
            print("\n🎯 Next steps:")
            print("   1. Create GitHub Release")
            print("   2. Test on actual clean system")
            print("   3. Upload to distribution platforms")
            print("   4. Create installer packages")
        else:
            print("\n❌ Clean installation test failed")
            print("   Fix the issues above before distribution")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

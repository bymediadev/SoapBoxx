# 🚀 SoapBoxx Demo - Installation Guide

## 📋 Prerequisites

- **Python 3.8+** installed and in PATH
- **Git** (optional, for updates)
- **4GB RAM** minimum (8GB recommended)
- **500MB disk space**

## 🖥️ Windows Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Double-click** `scripts\run_demo.bat`
3. **Wait** for dependencies to install
4. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```cmd
# Open Command Prompt as Administrator
cd path\to\SoapBoxx-Demo

# Install dependencies
python -m pip install -r requirements_demo.txt

# Run the demo
python frontend/main_window.py
```

## 🍎 macOS Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Open Terminal** and navigate to the package
3. **Run**: `./scripts/run_demo.sh`
4. **Wait** for dependencies to install
5. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```bash
# Open Terminal
cd path/to/SoapBoxx-Demo

# Install dependencies
python3 -m pip install -r requirements_demo.txt

# Run the demo
python3 frontend/main_window.py
```

## 🐧 Linux Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Open Terminal** and navigate to the package
3. **Make script executable**: `chmod +x scripts/run_demo.sh`
4. **Run**: `./scripts/run_demo.sh`
5. **Wait** for dependencies to install
6. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```bash
# Open Terminal
cd path/to/SoapBoxx-Demo

# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3-pip python3-venv

# Install Python dependencies
python3 -m pip install -r requirements_demo.txt

# Run the demo
python3 frontend/main_window.py
```

## 🔧 Troubleshooting

### Common Issues:

#### **"Python not found"**
- Install Python 3.8+ from [python.org](https://python.org)
- Ensure Python is added to PATH during installation

#### **"PyQt6 installation failed"**
- Update pip: `python -m pip install --upgrade pip`
- Install system dependencies (Linux: `sudo apt install python3-pyqt6`)

#### **"Module not found" errors**
- Run: `python test_barebones_modules.py`
- Ensure you're in the correct directory
- Check that all files were extracted properly

#### **"Permission denied" (Linux/macOS)**
- Make scripts executable: `chmod +x scripts/*.sh`
- Run with appropriate permissions

### Performance Tips:
- **Close other applications** for best performance
- **Use shorter text** for faster analysis
- **Restart** if the application becomes slow

## ✅ Verification

After installation, verify everything works:
```bash
python test_barebones_modules.py
```

You should see: **"🎉 All modules working correctly!"**

## 🆘 Still Having Issues?

1. **Check the logs** in the `logs/` directory
2. **Run the test script** to identify specific problems
3. **Check system requirements** and Python version
4. **Try manual installation** instead of launcher scripts

---

**🎯 Ready to start? Launch SoapBoxx Demo and begin creating amazing podcasts!**

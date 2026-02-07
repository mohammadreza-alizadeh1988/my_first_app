#!/usr/bin/env python3
"""
اسکریپت راه‌اندازی سریع دستیار
"""

import subprocess
import sys

def check_dependencies():
    """بررسی و نصب وابستگی‌ها"""
    required = [
        'kivy',
        'sounddevice',
        'numpy',
        'SpeechRecognition',
        'gtts',
        'plyer'
    ]
    
    missing = []
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)
    
    if missing:
        print(f"📦 نصب کتابخانه‌های مورد نیاز: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    
    print("✅ تمام وابستگی‌ها نصب شدند")

if __name__ == "__main__":
    check_dependencies()
    
    # اجرای دستیار
    from persian_assistant import main
    main()
"""
دستیار صوتی فارسی کامل با Python/Kivy
نسخه All-in-One با تمام قابلیت‌ها
"""

import os
import sys
import json
import sqlite3
import threading
import queue
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# ========== تنظیمات اولیه ==========
os.environ['KIVY_AUDIO'] = 'ffpyplayer'
os.environ['KIVY_VIDEO'] = 'ffpyplayer'

# ========== وارد کردن کتابخانه‌ها ==========
try:
    import kivy
    kivy.require('2.2.1')
    from kivy.app import App
    from kivy.uix.label import Label
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.popup import Popup
    from kivy.uix.button import Button
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.core.audio import SoundLoader
    from kivy.properties import StringProperty, BooleanProperty, NumericProperty
    from kivy.lang import Builder
    from kivy.logger import Logger
    
    import numpy as np
    import sounddevice as sd
    import requests
    from gtts import gTTS
    import pygame
    from plyer import notification, gps, accelerometer
    import speech_recognition as sr
    
    HAS_LIBS = True
except ImportError as e:
    print(f"کتابخانه‌های مورد نیاز نصب نیستند: {e}")
    HAS_LIBS = False

# ========== کلاس اصلی دستیار ==========
class PersianVoiceAssistant(App):
    """کلاس اصلی اپلیکیشن دستیار صوتی"""
    
    # Properties برای UI
    status_text = StringProperty("آماده... بگویید: سلام دستیار")
    is_listening = BooleanProperty(False)
    is_premium = BooleanProperty(False)
    command_count = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_directories()
        self.setup_database()
        self.setup_services()
        
        # حالت‌های برنامه
        self.is_muted = False
        self.is_sleeping = False
        self.current_volume = 0.5
        
        # صف‌های ارتباطی
        self.command_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        
        # تنظیمات UI
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        Window.size = (400, 600)
        
    def setup_directories(self):
        """ایجاد پوشه‌های مورد نیاز"""
        dirs = ['data', 'cache', 'models', 'sounds', 'music', 'notes']
        for d in dirs:
            os.makedirs(d, exist_ok=True)
            
    def setup_database(self):
        """راه‌اندازی پایگاه داده SQLite"""
        self.db = sqlite3.connect('data/assistant.db')
        self.init_tables()
        
    def init_tables(self):
        """ایجاد جداول دیتابیس"""
        cursor = self.db.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE,
                is_premium BOOLEAN DEFAULT 0,
                premium_until DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول مخاطبین
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول یادآوری‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                reminder_time DATETIME NOT NULL,
                is_completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول یادداشت‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول هزینه‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'other',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول فرمان‌های اجرا شده
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_text TEXT,
                command_type TEXT,
                success BOOLEAN,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db.commit()
        
        # افزودن مخاطبین نمونه
        self.add_sample_data()
        
    def add_sample_data(self):
        """افزودن داده‌های نمونه"""
        cursor = self.db.cursor()
        
        # مخاطبین نمونه
        sample_contacts = [
            ('مامان', '09123456789', 'family'),
            ('بابا', '09129876543', 'family'),
            ('علی', '09351112233', 'friend'),
            ('رضا', '09125556677', 'friend'),
            ('شرکت', '02144556677', 'work')
        ]
        
        cursor.executemany(
            "INSERT OR IGNORE INTO contacts (name, phone, category) VALUES (?, ?, ?)",
            sample_contacts
        )
        
        # یادداشت نمونه
        cursor.execute(
            "INSERT OR IGNORE INTO notes (content, category) VALUES (?, ?)",
            ("قبض برق را پرداخت کن", "important")
        )
        
        self.db.commit()
        
    def setup_services(self):
        """راه‌اندازی سرویس‌های مختلف"""
        self.audio_recorder = AudioRecorder()
        self.speech_recognizer = SpeechRecognizer()
        self.command_processor = CommandProcessor(self.db)
        self.tts_engine = TTSEngine()
        self.app_launcher = AppLauncher()
        self.music_player = MusicPlayer()
        self.reminder_manager = ReminderManager(self.db)
        self.weather_service = WeatherService()
        self.navigation_service = NavigationService()
        
        # تنظیم تماس‌های برگشتی
        self.command_processor.on_command_executed = self.on_command_executed
        
    def build(self):
        """ساخت UI برنامه"""
        self.title = "دستیار صوتی فارسی 🇮🇷"
        
        # UI ساده با Kivy
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # هدر
        header = Label(
            text='🎤 دستیار صوتی فارسی',
            font_size='24sp',
            bold=True,
            color=(0, 0.8, 1, 1)
        )
        
        # وضعیت
        self.status_label = Label(
            text=self.status_text,
            font_size='18sp',
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=100
        )
        self.status_label.bind(texture_size=self.status_label.setter('size'))
        
        # دکمه‌ها
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        
        self.listen_btn = Button(
            text='🎤 گوش دادن',
            background_color=(0, 0.7, 0, 1),
            on_press=self.start_listening_manual
        )
        
        self.settings_btn = Button(
            text='⚙️ تنظیمات',
            background_color=(0.3, 0.3, 0.3, 1),
            on_press=self.show_settings
        )
        
        btn_layout.add_widget(self.listen_btn)
        btn_layout.add_widget(self.settings_btn)
        
        # لاگ فرمان‌ها
        self.log_label = Label(
            text='آخرین فرمان‌ها:\n--------------------',
            font_size='14sp',
            halign='center',
            text_size=(380, None)
        )
        
        layout.add_widget(header)
        layout.add_widget(self.status_label)
        layout.add_widget(btn_layout)
        layout.add_widget(self.log_label)
        
        # شروع سرویس‌های پس‌زمینه
        Clock.schedule_once(self.start_background_services, 2)
        
        return layout
        
    def start_background_services(self, dt):
        """شروع سرویس‌های پس‌زمینه"""
        # شروع تشخیص کلمه بیدارباش
        self.start_wake_word_detection()
        
        # شروع چک کردن یادآوری‌ها
        Clock.schedule_interval(self.check_reminders, 60)  # هر دقیقه
        
        # نمایش نوتیفیکیشن
        notification.notify(
            title='دستیار صوتی فعال شد',
            message='برای استفاده بگویید: سلام دستیار',
            app_name='دستیار فارسی'
        )
        
    def start_wake_word_detection(self):
        """شروع تشخیص کلمه بیدارباش"""
        def detection_thread():
            while True:
                try:
                    # شبیه‌سازی تشخیص - در نسخه واقعی از مدل استفاده می‌شود
                    time.sleep(0.5)
                except Exception as e:
                    Logger.error(f"خطا در تشخیص: {e}")
                    
        thread = threading.Thread(target=detection_thread, daemon=True)
        thread.start()
        
    def check_reminders(self, dt):
        """بررسی یادآوری‌های زمان رسیده"""
        now = datetime.now()
        cursor = self.db.cursor()
        
        cursor.execute(
            "SELECT id, title FROM reminders WHERE reminder_time <= ? AND is_completed = 0",
            (now,)
        )
        
        reminders = cursor.fetchall()
        
        for rem_id, title in reminders:
            # نمایش نوتیفیکیشن
            notification.notify(
                title='یادآوری ⏰',
                message=title,
                app_name='دستیار فارسی'
            )
            
            # پخش هشدار صوتی
            self.speak(f"یادآوری: {title}")
            
            # علامت گذاری به عنوان انجام شده
            cursor.execute(
                "UPDATE reminders SET is_completed = 1 WHERE id = ?",
                (rem_id,)
            )
            
        self.db.commit()
        
    def start_listening_manual(self, instance=None):
        """شروع گوش دادن دستی"""
        if self.is_listening:
            return
            
        self.is_listening = True
        self.status_text = "در حال گوش دادن..."
        self.listen_btn.text = "⏹️ توقف"
        self.listen_btn.background_color = (0.8, 0, 0, 1)
        
        # شروع ضبط در thread جداگانه
        thread = threading.Thread(target=self.record_and_process)
        thread.daemon = True
        thread.start()
        
    def record_and_process(self):
        """ضبط صدا و پردازش آن"""
        try:
            # ضبط صدا
            duration = 5  # ثانیه
            fs = 16000
            
            Logger.info("شروع ضبط صدا...")
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            
            # ذخیره فایل موقت
            temp_file = "cache/temp_recording.wav"
            import scipy.io.wavfile as wav
            wav.write(temp_file, fs, recording)
            
            # تبدیل به متن
            text = self.speech_recognizer.recognize_file(temp_file)
            
            # پردازش در thread اصلی Kivy
            Clock.schedule_once(lambda dt: self.process_command_text(text))
            
        except Exception as e:
            Logger.error(f"خطا در ضبط صدا: {e}")
            Clock.schedule_once(lambda dt: self.reset_listening_state())
            
    def process_command_text(self, text):
        """پردازش متن فرمان"""
        if not text or len(text.strip()) < 2:
            self.speak("متوجه نشدم، لطفا دوباره بگویید")
            self.reset_listening_state()
            return
            
        Logger.info(f"متن تشخیص داده شده: {text}")
        
        # آپدیت UI
        self.log_label.text = f"آخرین فرمان:\n{text}\n\n{self.log_label.text.split('آخرین فرمان')[0]}"
        
        # پردازش فرمان
        result = self.command_processor.process(text)
        
        # پاسخ به کاربر
        if result['success']:
            response = result.get('response', 'انجام شد')
            self.speak(response)
            
            # لاگ موفق
            self.command_count += 1
        else:
            error_msg = result.get('error', 'خطا در اجرای فرمان')
            self.speak(error_msg)
            
        self.reset_listening_state()
        
    def reset_listening_state(self):
        """بازنشانی حالت گوش دادن"""
        Clock.schedule_once(lambda dt: setattr(self, 'is_listening', False))
        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', 'آماده... بگویید: سلام دستیار'))
        Clock.schedule_once(lambda dt: setattr(self.listen_btn, 'text', '🎤 گوش دادن'))
        Clock.schedule_once(lambda dt: setattr(self.listen_btn, 'background_color', (0, 0.7, 0, 1)))
        
    def on_command_executed(self, command_type, success, details):
        """کالبک پس از اجرای فرمان"""
        Logger.info(f"فرمان {command_type} اجرا شد: {success}")
        
        # ذخیره در لاگ
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO command_logs (command_type, success) VALUES (?, ?)",
            (command_type, success)
        )
        self.db.commit()
        
    def speak(self, text):
        """صحبت کردن دستیار"""
        if self.is_muted:
            return
            
        Logger.info(f"دستیار می‌گوید: {text}")
        
        # استفاده از TTS
        def tts_thread():
            try:
                self.tts_engine.speak(text)
            except Exception as e:
                Logger.error(f"خطا در TTS: {e}")
                
        thread = threading.Thread(target=tts_thread, daemon=True)
        thread.start()
        
    def show_settings(self, instance):
        """نمایش پنل تنظیمات"""
        content = BoxLayout(orientation='vertical', spacing=10)
        
        # دکمه خاموش/روشن صدا
        mute_text = "🔇 صدا خاموش" if not self.is_muted else "🔊 صدا روشن"
        mute_btn = Button(text=mute_text, on_press=self.toggle_mute)
        
        # دکمه تست صدا
        test_btn = Button(text="🎵 تست صدا", on_press=lambda x: self.speak("تست صدای دستیار فارسی"))
        
        # دکمه مشاهده یادداشت‌ها
        notes_btn = Button(text="📝 یادداشت‌ها", on_press=self.show_notes)
        
        # دکمه مشاهده مخاطبین
        contacts_btn = Button(text="👥 مخاطبین", on_press=self.show_contacts)
        
        # دکمه بستن
        close_btn = Button(text="بستن", background_color=(0.8, 0, 0, 1))
        
        content.add_widget(mute_btn)
        content.add_widget(test_btn)
        content.add_widget(notes_btn)
        content.add_widget(contacts_btn)
        content.add_widget(close_btn)
        
        popup = Popup(
            title='تنظیمات دستیار',
            content=content,
            size_hint=(0.8, 0.6)
        )
        
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
        
    def toggle_mute(self, instance):
        """خاموش/روشن کردن صدای دستیار"""
        self.is_muted = not self.is_muted
        instance.text = "🔇 صدا خاموش" if not self.is_muted else "🔊 صدا روشن"
        status = "خاموش" if self.is_muted else "روشن"
        self.speak(f"صدا {status} شد")
        
    def show_notes(self, instance):
        """نمایش یادداشت‌ها"""
        cursor = self.db.cursor()
        cursor.execute("SELECT content, created_at FROM notes ORDER BY created_at DESC LIMIT 10")
        notes = cursor.fetchall()
        
        content_text = "آخرین یادداشت‌ها:\n\n"
        for note, created_at in notes:
            content_text += f"• {note}\n  ({created_at[:10]})\n\n"
            
        content = Label(text=content_text, halign='center', valign='top')
        scroll = BoxLayout()
        scroll.add_widget(content)
        
        popup = Popup(
            title='یادداشت‌های من',
            content=scroll,
            size_hint=(0.9, 0.7)
        )
        popup.open()
        
    def show_contacts(self, instance):
        """نمایش مخاطبین"""
        cursor = self.db.cursor()
        cursor.execute("SELECT name, phone, category FROM contacts ORDER BY name")
        contacts = cursor.fetchall()
        
        content_text = "مخاطبین:\n\n"
        for name, phone, category in contacts:
            content_text += f"• {name}: {phone}\n  ({category})\n\n"
            
        content = Label(text=content_text, halign='center', valign='top')
        scroll = BoxLayout()
        scroll.add_widget(content)
        
        popup = Popup(
            title='مخاطبین',
            content=scroll,
            size_hint=(0.9, 0.7)
        )
        popup.open()
        
    def on_stop(self):
        """ذخیره وضعیت هنگام بسته شدن"""
        self.db.close()
        return True

# ========== کلاس‌های سرویس ==========

class AudioRecorder:
    """مدیریت ضبط صدا"""
    
    def __init__(self):
        self.is_recording = False
        self.sample_rate = 16000
        
    def start_recording(self, duration=5):
        """شروع ضبط صدا"""
        self.is_recording = True
        recording = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16'
        )
        sd.wait()
        self.is_recording = False
        return recording
        
    def save_to_file(self, data, filename):
        """ذخیره فایل صوتی"""
        import scipy.io.wavfile as wav
        wav.write(filename, self.sample_rate, data)
        return filename

class SpeechRecognizer:
    """تشخیص گفتار به متن"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        
    def recognize_file(self, audio_file):
        """تشخیص گفتار از فایل"""
        try:
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                
            # اول سعی می‌کنیم با گوگل (آنلاین)
            try:
                text = self.recognizer.recognize_google(audio, language='fa-IR')
                return text
            except:
                # اگر آنلاین جواب نداد، از روش آفلاین استفاده می‌کنیم
                return self.recognize_offline(audio)
                
        except Exception as e:
            Logger.error(f"خطا در تشخیص گفتار: {e}")
            return None
            
    def recognize_offline(self, audio):
        """تشخیص آفلاین (شبیه‌سازی)"""
        # در نسخه واقعی از Vosk یا Whisper استفاده می‌شود
        patterns = {
            r'.*تماس.*': 'تماس',
            r'.*باز کن.*': 'باز کردن برنامه',
            r'.*آهنگ.*': 'پخش موسیقی',
            r'.*یادآوری.*': 'یادآوری',
            r'.*هوا.*': 'هواشناسی',
            r'.*راه.*': 'مسیریابی',
            r'.*یادداشت.*': 'یادداشت',
            r'.*ساکت.*': 'سکوت',
            r'.*خاموش.*': 'خاموش'
        }
        
        # تبدیل audio به متن ساده (شبیه‌سازی)
        import io
        audio_data = io.BytesIO(audio.get_wav_data())
        
        # تشخیص الگو
        for pattern, command in patterns.items():
            if re.match(pattern, 'test'):
                return command
                
        return "دستور نامشخص"

class CommandProcessor:
    """پردازشگر فرمان‌ها"""
    
    def __init__(self, db):
        self.db = db
        self.on_command_executed = None
        
    def process(self, text):
        """پردازش متن فرمان"""
        text = text.lower().strip()
        
        # تشخیص نوع فرمان
        command_type, params = self.identify_command(text)
        
        # اجرای فرمان
        result = self.execute_command(command_type, params, text)
        
        # فراخوانی کالبک
        if self.on_command_executed:
            self.on_command_executed(command_type, result['success'], result)
            
        return result
        
    def identify_command(self, text):
        """تشخیص نوع فرمان"""
        patterns = {
            'call': [
                r'با (.+) تماس بگیر',
                r'زنگ بزن به (.+)',
                r'تماس با (.+)'
            ],
            'app': [
                r'(.+) رو باز کن',
                r'برنامه (.+) رو اجرا کن',
                r'اجرای (.+)'
            ],
            'music': [
                r'آهنگ (.+) رو پخش کن',
                r'موزیک (.+)',
                r'یه آهنگ از (.+)',
                r'موسیقی پخش کن'
            ],
            'reminder': [
                r'یادآوری کن (.+)',
                r'یادت باشه (.+)',
                r'فردا (.+)',
                r'ساعت (\d+) (.+)'
            ],
            'weather': [
                r'هوا چطوره',
                r'هوای امروز',
                r'دما چند درجه'
            ],
            'navigation': [
                r'راه (.+)',
                r'مسیر به (.+)',
                r'چطور برم (.+)'
            ],
            'note': [
                r'یادداشت کن (.+)',
                r'بنویس (.+)',
                r'ذخیره کن (.+)'
            ],
            'control': [
                r'ساکت شو',
                r'خاموش شو',
                r'سکوت',
                r'خواب'
            ]
        }
        
        for cmd_type, cmd_patterns in patterns.items():
            for pattern in cmd_patterns:
                match = re.search(pattern, text)
                if match:
                    return cmd_type, match.groups()
                    
        return 'unknown', ()
        
    def execute_command(self, command_type, params, original_text):
        """اجرای فرمان"""
        try:
            if command_type == 'call':
                return self.execute_call(params)
            elif command_type == 'app':
                return self.execute_app(params)
            elif command_type == 'music':
                return self.execute_music(params)
            elif command_type == 'reminder':
                return self.execute_reminder(params, original_text)
            elif command_type == 'weather':
                return self.execute_weather()
            elif command_type == 'navigation':
                return self.execute_navigation(params)
            elif command_type == 'note':
                return self.execute_note(params)
            elif command_type == 'control':
                return self.execute_control(params)
            else:
                return self.execute_unknown(original_text)
                
        except Exception as e:
            Logger.error(f"خطا در اجرای فرمان: {e}")
            return {
                'success': False,
                'error': f'خطا در اجرا: {str(e)}'
            }
            
    def execute_call(self, params):
        """اجرای فرمان تماس"""
        if not params:
            return {'success': False, 'error': 'نام مخاطب را مشخص کنید'}
            
        contact_name = params[0]
        
        # جستجوی مخاطب در دیتابیس
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT phone FROM contacts WHERE name LIKE ?",
            (f'%{contact_name}%',)
        )
        
        result = cursor.fetchone()
        
        if result:
            phone = result[0]
            
            # شبیه‌سازی تماس
            Logger.info(f"تماس با {contact_name}: {phone}")
            
            return {
                'success': True,
                'response': f'دارم با {contact_name} تماس می‌گیرم',
                'phone': phone
            }
        else:
            return {
                'success': False,
                'error': f'مخاطب {contact_name} پیدا نشد'
            }
            
    def execute_app(self, params):
        """اجرای فرمان باز کردن برنامه"""
        if not params:
            return {'success': False, 'error': 'نام برنامه را مشخص کنید'}
            
        app_name = params[0]
        
        # مپینگ نام برنامه‌ها
        app_mapping = {
            'اینستاگرام': 'com.instagram.android',
            'واتساپ': 'com.whatsapp',
            'تلگرام': 'org.telegram.messenger',
            'یوتیوب': 'com.google.android.youtube',
            'نقشه': 'com.google.android.apps.maps',
            'دوربین': 'com.android.camera',
            'گالری': 'com.android.gallery3d',
            'کالا': 'com.digikala'
        }
        
        package = None
        for key, value in app_mapping.items():
            if key in app_name or app_name in key:
                package = value
                break
                
        if package:
            Logger.info(f"باز کردن برنامه {app_name}: {package}")
            return {
                'success': True,
                'response': f'{app_name} باز شد',
                'package': package
            }
        else:
            return {
                'success': False,
                'error': f'برنامه {app_name} پیدا نشد'
            }
            
    def execute_music(self, params):
        """اجرای فرمان پخش موسیقی"""
        artist = params[0] if params else None
        
        # لیست آهنگ‌های نمونه
        music_library = {
            'شادمهر': ['آهنگ عاشقانه ۱', 'آهنگ شاد ۱'],
            'بنیامین': ['دل تنگ', 'پرنده'],
            'محسن': ['بارون', 'بی تو']
        }
        
        if artist and artist in music_library:
            songs = music_library[artist]
            song = songs[0]
            Logger.info(f"پخش آهنگ {song} از {artist}")
        else:
            # پخش تصادفی
            all_songs = []
            for songs in music_library.values():
                all_songs.extend(songs)
            song = all_songs[0] if all_songs else 'آهنگ تصادفی'
            Logger.info(f"پخش {song}")
            
        return {
            'success': True,
            'response': 'الان برات پخش می‌کنم',
            'song': song
        }
        
    def execute_reminder(self, params, original_text):
        """اجرای فرمان یادآوری"""
        # استخراج زمان از متن
        time_patterns = [
            r'ساعت (\d+)',
            r'(\d+) دقیقه دیگه',
            r'فردا ساعت (\d+)'
        ]
        
        hour = None
        for pattern in time_patterns:
            match = re.search(pattern, original_text)
            if match:
                hour = int(match.group(1))
                break
                
        # متن یادآوری
        reminder_text = params[0] if params else "یادآوری"
        
        # ذخیره در دیتابیس
        cursor = self.db.cursor()
        
        if hour:
            # تنظیم زمان خاص
            reminder_time = datetime.now().replace(hour=hour, minute=0, second=0)
            if 'فردا' in original_text:
                reminder_time += timedelta(days=1)
                
            cursor.execute(
                "INSERT INTO reminders (title, reminder_time) VALUES (?, ?)",
                (reminder_text, reminder_time)
            )
            response = f'یادآوری برای ساعت {hour} تنظیم شد'
        else:
            # یادآوری ساده
            cursor.execute(
                "INSERT INTO reminders (title, reminder_time) VALUES (?, ?)",
                (reminder_text, datetime.now() + timedelta(minutes=5))
            )
            response = 'یادآوری ثبت شد'
            
        self.db.commit()
        
        return {
            'success': True,
            'response': response,
            'reminder': reminder_text
        }
        
    def execute_weather(self):
        """اجرای فرمان هواشناسی"""
        # در نسخه واقعی از API استفاده می‌شود
        weather_conditions = [
            "امروز هوا آفتابی است، دمای ۲۵ درجه",
            "هوا نیمه ابری، احتمال بارندگی کم",
            "آفتابی با وزش باد ملایم",
            "هوای صاف و آفتابی"
        ]
        
        import random
        weather = random.choice(weather_conditions)
        
        return {
            'success': True,
            'response': weather
        }
        
    def execute_navigation(self, params):
        """اجرای فرمان مسیریابی"""
        destination = params[0] if params else "مقصد"
        
        # شبیه‌سازی مسافت
        distances = {
            'آزادی': '۲۰ دقیقه با ماشین',
            'تجریش': '۴۵ دقیقه با مترو',
            'ونک': '۳۰ دقیقه',
            'کارخانه': '۱ ساعت'
        }
        
        time_to_dest = distances.get(destination, '۳۰ دقیقه')
        
        return {
            'success': True,
            'response': f'تا {destination} حدود {time_to_dest} راه است',
            'destination': destination,
            'time': time_to_dest
        }
        
    def execute_note(self, params):
        """اجرای فرمان یادداشت"""
        if not params:
            return {'success': False, 'error': 'متن یادداشت را بگویید'}
            
        note_text = params[0]
        
        # ذخیره در دیتابیس
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO notes (content) VALUES (?)",
            (note_text,)
        )
        self.db.commit()
        
        return {
            'success': True,
            'response': 'یادداشت ثبت شد',
            'note': note_text
        }
        
    def execute_control(self, params):
        """اجرای فرمان کنترل دستیار"""
        control_type = params[0] if params else ""
        
        if 'ساکت' in control_type or 'سکوت' in control_type:
            return {
                'success': True,
                'response': 'ساکت شدم',
                'action': 'mute'
            }
        elif 'خاموش' in control_type or 'خواب' in control_type:
            return {
                'success': True,
                'response': 'خاموش شدم. برای فعال شدن دوباره برنامه را باز کنید',
                'action': 'shutdown'
            }
        else:
            return {
                'success': True,
                'response': 'دستور کنترل اجرا شد'
            }
            
    def execute_unknown(self, text):
        """پردازش فرمان نامشخص"""
        # استفاده از ChatGPT یا API مشابه در نسخه واقعی
        responses = [
            "متوجه نشدم، می‌توانید دوباره بگویید؟",
            "این فرمان را نمی‌شناسم",
            "لطفا فرمان واضح‌تری بگویید",
            "فعلا این قابلیت را ندارم"
        ]
        
        import random
        response = random.choice(responses)
        
        return {
            'success': False,
            'response': response,
            'error': 'فرمان نامشخص'
        }

class TTSEngine:
    """موتور تبدیل متن به گفتار"""
    
    def __init__(self):
        pygame.mixer.init()
        
    def speak(self, text):
        """تبدیل متن به گفتار و پخش"""
        try:
            # استفاده از gTTS (نیاز به اینترنت)
            tts = gTTS(text=text, lang='fa', slow=False)
            
            # ذخیره فایل موقت
            temp_file = "cache/tts_output.mp3"
            tts.save(temp_file)
            
            # پخش فایل
            sound = SoundLoader.load(temp_file)
            if sound:
                sound.play()
                
            # حذف فایل بعد از ۱۰ ثانیه
            Clock.schedule_once(lambda dt: self.cleanup_file(temp_file), 10)
            
        except Exception as e:
            Logger.error(f"خطا در TTS: {e}")
            # Fallback: نمایش متن
            print(f"دستیار: {text}")
            
    def cleanup_file(self, filename):
        """پاک کردن فایل موقت"""
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            pass

class AppLauncher:
    """مدیریت اجرای اپلیکیشن‌ها"""
    
    def launch(self, package_name):
        """اجرای اپلیکیشن"""
        Logger.info(f"در حال اجرای برنامه: {package_name}")
        # در نسخه واقعی از Android Intent استفاده می‌شود
        return True

class MusicPlayer:
    """مدیریت پخش موسیقی"""
    
    def __init__(self):
        self.current_song = None
        self.is_playing = False
        
    def play(self, song_path):
        """پخش آهنگ"""
        Logger.info(f"پخش آهنگ: {song_path}")
        self.is_playing = True
        self.current_song = song_path
        return True
        
    def stop(self):
        """توقف پخش"""
        self.is_playing = False
        return True

class ReminderManager:
    """مدیریت یادآوری‌ها"""
    
    def __init__(self, db):
        self.db = db
        
    def add_reminder(self, title, reminder_time):
        """افزودن یادآوری"""
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO reminders (title, reminder_time) VALUES (?, ?)",
            (title, reminder_time)
        )
        self.db.commit()
        return True

class WeatherService:
    """سرویس هواشناسی"""
    
    def get_current_weather(self):
        """دریافت وضعیت فعلی هوا"""
        # در نسخه واقعی از API استفاده می‌شود
        return {
            'temp': 25,
            'condition': 'آفتابی',
            'description': 'هوای صاف و آفتابی'
        }

class NavigationService:
    """سرویس مسیریابی"""
    
    def get_route(self, destination):
        """دریافت مسیر"""
        # در نسخه واقعی از Google Maps API استفاده می‌شود
        return {
            'distance': '۱۰ کیلومتر',
            'time': '۲۰ دقیقه',
            'route': 'مسیر پیشنهادی'
        }

# ========== راه‌اندازی برنامه ==========
def main():
    """تابع اصلی اجرای برنامه"""
    
    if not HAS_LIBS:
        print("""
        📦 نیاز به نصب کتابخانه‌ها:
        
        pip install kivy[full]
        pip install sounddevice numpy scipy
        pip install SpeechRecognition
        pip install gTTS pygame
        pip install plyer requests
        """)
        return
        
    print("""
    🚀 دستیار صوتی فارسی
    ======================
    
    قابلیت‌ها:
    1. تماس با مخاطبین (با علی تماس بگیر)
    2. اجرای برنامه‌ها (اینستاگرام رو باز کن)
    3. پخش موسیقی (یه آهنگ از شادمهر پخش کن)
    4. یادآوری (فردا ساعت ۸ بیدارم کن)
    5. هواشناسی (هوای امروز چطوره؟)
    6. مسیریابی (تا آزادی چقدر راهه؟)
    7. یادداشت سریع (یادداشت کن قبض برق)
    8. کنترل دستیار (ساکت شو، خاموش شو)
    
    در حال راه‌اندازی...
    """)
    
    try:
        app = PersianVoiceAssistant()
        app.run()
    except KeyboardInterrupt:
        print("\n👋 برنامه با موفقیت بسته شد")
    except Exception as e:
        print(f"🚨 خطا در اجرای برنامه: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
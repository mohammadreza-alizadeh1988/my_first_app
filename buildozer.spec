[app]
title = دستیار صوتی فارسی
package.name = persianvoiceassistant
package.domain = ir.assistant
version = 1.0
source.dir = .
source.include_exts = py,png,jpg,kv,ttf,json,wav,mp3,db
requirements = python3,kivy==2.2.1,numpy,requests,gtts,plyer,SpeechRecognition
android.permissions = INTERNET,RECORD_AUDIO,READ_CONTACTS,CALL_PHONE,ACCESS_FINE_LOCATION
android.api = 33
android.minapi = 24
presplash.filename = %(source.dir)s/data/logo.png
icon.filename = %(source.dir)s/data/icon.png
orientation = portrait
fullscreen = 0
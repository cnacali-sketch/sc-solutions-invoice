[app]
title = SC Solutions
package.name = scsolutions
package.domain = org.scsolutions

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json

version = 1.0

requirements = python3,kivy==2.3.0,reportlab,num2words,pillow,plyer

orientation = portrait

fullscreen = 0

android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,INTERNET

android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33

android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True

android.target_sdk = 33

android.manifest.intent_filters = 

# Add icons (optional - replace with your own PNGs)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

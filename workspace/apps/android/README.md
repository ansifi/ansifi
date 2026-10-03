# Ansif Workspace — Android

WebView of the hub. While the **A** desktop app is open on the same Wi-Fi, the phone uses:

**http://ansif-workspace.local:4040/**

The app finds that name (or the PC LAN IP) by itself. Hub URL → Find desktop to retry.

Build:

```bash
export ANDROID_HOME=/home/ansif/Android/Sdk
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew assembleDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. Install file on Drive:

https://drive.google.com/open?id=1bMBXfU3ZT5YRjgxzayGDJkvA_30bKYfs

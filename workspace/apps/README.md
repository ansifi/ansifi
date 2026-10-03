# Desktop (Electron) and phone (Android) wrappers for the local hub.

On this PC the window uses `http://127.0.0.1:4040/`. The phone uses **http://ansif-workspace.local:4040/** while the desktop app is running (same Wi-Fi).

## Desktop

```bash
apps/desktop/launch.sh
```

Dock **A** starts `./run.sh lan` and publishes the phone URL. File → Copy phone URL.

## Android

Debug APK: `apps/android/app/build/outputs/apk/debug/app-debug.apk` (Drive `works/00_Ansif/apps/`).

Open the **A** desktop app, then open the phone app. It looks for `http://ansif-workspace.local:4040/`.

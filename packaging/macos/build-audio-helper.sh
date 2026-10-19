#!/usr/bin/env bash
# Build cctl-audio.app and install it only to an explicitly approved new destination.
# The first capture asks for Screen & System Audio Recording (and Microphone, for --mic) for this app.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
BUILD="$HERE/build"
APP="${CCTL_AUDIO_APP:?Set an absolute new approved app destination}"
# Validate BOTH raw paths before writes; reserve new app/build exclusively.
# Static checks only: operator-controlled parents, no hostile ancestor races.
python3 -I -S "$HERE/audio_destination_guard.py" "$APP" "$BUILD"
swiftc -O -parse-as-library -o "$BUILD/cctl-audio" "$HERE/cctl-audio/main.swift" \
  -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
mkdir -p "$APP/Contents/MacOS"
cp "$BUILD/cctl-audio" "$APP/Contents/MacOS/cctl-audio"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>dev.computer-ctrl.audio</string>
  <key>CFBundleName</key><string>cctl-audio</string>
  <key>CFBundleExecutable</key><string>cctl-audio</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>cctl records the microphone when an agent asks for audio_capture source=mic.</string>
  <key>NSAudioCaptureUsageDescription</key><string>cctl records system audio when an agent asks for audio_capture.</string>
</dict>
</plist>
PLIST
# Choose an identity explicitly with CCTL_AUDIO_SIGN, otherwise sign ad-hoc.
# An ad-hoc signature changes on rebuild and can reset macOS privacy grants.
SIGN="${CCTL_AUDIO_SIGN:--}"
codesign --force --sign "${SIGN:--}" --identifier dev.computer-ctrl.audio "$APP"
echo "signed with: ${SIGN:-ad-hoc (privacy grants reset on every rebuild)}"
echo "installed $APP"

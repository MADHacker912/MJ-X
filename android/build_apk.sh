#!/usr/bin/env bash
set -e

BUILD_TOOLS="/home/obito/Android/Sdk/build-tools/37.0.0"
PLATFORM="/home/obito/Android/Sdk/platforms/android-34/android.jar"
WORK_DIR="/home/obito/Documents/MJ-X/android"

echo "=== Building MJ-X Android APK ==="
rm -rf "$WORK_DIR/build"
mkdir -p "$WORK_DIR/build/compiled_res"
mkdir -p "$WORK_DIR/build/gen"
mkdir -p "$WORK_DIR/build/classes"
mkdir -p "$WORK_DIR/build/dex"
mkdir -p "$WORK_DIR/bin"

echo "1. Compiling resources..."
$BUILD_TOOLS/aapt2 compile --dir "$WORK_DIR/app/src/main/res" -o "$WORK_DIR/build/compiled_res.zip"

echo "2. Linking resources & generating R.java..."
$BUILD_TOOLS/aapt2 link -o "$WORK_DIR/build/base.apk" \
  -I "$PLATFORM" \
  --manifest "$WORK_DIR/app/src/main/AndroidManifest.xml" \
  --java "$WORK_DIR/build/gen" \
  --auto-add-overlay \
  "$WORK_DIR/build/compiled_res.zip"

echo "3. Compiling Java sources..."
javac -source 17 -target 17 \
  -cp "$PLATFORM" \
  -d "$WORK_DIR/build/classes" \
  $(find "$WORK_DIR/build/gen" "$WORK_DIR/app/src/main/java" -name "*.java")

echo "4. Dexing bytecode..."
$BUILD_TOOLS/d8 --lib "$PLATFORM" \
  --output "$WORK_DIR/build/dex" \
  $(find "$WORK_DIR/build/classes" -name "*.class")

echo "5. Assembling package..."
cp "$WORK_DIR/build/base.apk" "$WORK_DIR/build/unaligned.apk"
cd "$WORK_DIR/build/dex"
zip -uj "$WORK_DIR/build/unaligned.apk" classes.dex
cd "$WORK_DIR"

echo "6. Aligning APK..."
$BUILD_TOOLS/zipalign -f -p 4 "$WORK_DIR/build/unaligned.apk" "$WORK_DIR/bin/MJ-X-Assistant-aligned.apk"

echo "7. Signing APK..."
KEYSTORE="$WORK_DIR/build/debug.keystore"
keytool -genkey -v -keystore "$KEYSTORE" -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" 2>/dev/null

$BUILD_TOOLS/apksigner sign --ks "$KEYSTORE" --ks-pass pass:android --out "$WORK_DIR/bin/MJ-X-Assistant.apk" "$WORK_DIR/bin/MJ-X-Assistant-aligned.apk"

rm -f "$WORK_DIR/bin/MJ-X-Assistant-aligned.apk"
echo "=== BUILD SUCCESSFUL ==="
ls -lh "$WORK_DIR/bin/MJ-X-Assistant.apk"

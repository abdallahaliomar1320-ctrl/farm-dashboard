$ErrorActionPreference = "Stop"

$androidHome = "$env:LOCALAPPDATA\Android\Sdk"
$cmdlineToolsDir = "$androidHome\cmdline-tools"
$latestDir = "$cmdlineToolsDir\latest"

Write-Host "Creating Android SDK directories at $androidHome..."
New-Item -Path $cmdlineToolsDir -ItemType Directory -Force | Out-Null

$url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
$zipPath = "$env:TEMP\cmdline-tools.zip"

Write-Host "Downloading Android Command Line Tools (~114MB)..."
Invoke-WebRequest -Uri $url -OutFile $zipPath

Write-Host "Extracting Command Line Tools..."
if (Test-Path "$cmdlineToolsDir\cmdline-tools") {
    Remove-Item -Path "$cmdlineToolsDir\cmdline-tools" -Recurse -Force
}
if (Test-Path $latestDir) {
    Remove-Item -Path $latestDir -Recurse -Force
}

Expand-Archive -Path $zipPath -DestinationPath $cmdlineToolsDir -Force
Rename-Item -Path "$cmdlineToolsDir\cmdline-tools" -NewName "latest" -Force

$sdkmanager = "$latestDir\bin\sdkmanager.bat"
$avdmanager = "$latestDir\bin\avdmanager.bat"

Write-Host "Accepting all Android SDK licenses..."
cmd.exe /c "(for /l %i in (1,1,20) do @echo y) | `"$sdkmanager`" --licenses"

Write-Host "Downloading and installing Android SDK components (This will take a while, ~1.5 GB)..."
cmd.exe /c "`"$sdkmanager`" `"platform-tools`" `"platforms;android-34`" `"build-tools;34.0.0`" `"system-images;android-34;google_apis_playstore;x86_64`" `"emulator`""

Write-Host "Creating Android Virtual Device (AVD) named 'FlutterEmulator'..."
cmd.exe /c "echo no | `"$avdmanager`" create avd -n FlutterEmulator -k `"system-images;android-34;google_apis_playstore;x86_64`" --force"

Write-Host "Linking Android SDK to Flutter..."
flutter config --android-sdk "$androidHome"

Write-Host "=============================================="
Write-Host "Android Emulator setup completed successfully!"
Write-Host "=============================================="

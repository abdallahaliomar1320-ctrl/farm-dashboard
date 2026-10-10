$ErrorActionPreference = "Stop"
$AndroidHome = "C:\AndroidSDK"
$CmdLineToolsZip = "$AndroidHome\cmdline-tools.zip"
$CmdLineToolsDir = "$AndroidHome\cmdline-tools"
$LatestDir = "$CmdLineToolsDir\latest"

Write-Host "4. Installing required Android platforms and tools..."
$SdkManager = "$LatestDir\bin\sdkmanager.bat"
$env:ANDROID_HOME = $AndroidHome
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21"

# Provide 'y' continuously for licenses
$yes = "y`n" * 100
Write-Output $yes | & $SdkManager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

Write-Host "5. Accepting Android Licenses..."
Write-Output $yes | & $SdkManager --licenses

Write-Host "6. Configuring Flutter..."
flutter config --android-sdk $AndroidHome
Write-Output $yes | flutter doctor --android-licenses

Write-Host "Done! SDK installed successfully."

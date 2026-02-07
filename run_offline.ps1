Write-Host "Flutter Offline Runner" -ForegroundColor Cyan

# Remove cupertino_icons from pubspec.yaml
(Get-Content "pubspec.yaml") |
Where-Object { $_ -notmatch "cupertino_icons" } |
Set-Content "pubspec.yaml"

Write-Host "✔ pubspec.yaml updated" -ForegroundColor Green

# Remove Cupertino imports from main.dart
(Get-Content "lib\main.dart") |
Where-Object { $_ -notmatch "Cupertino" } |
Set-Content "lib\main.dart"

Write-Host "✔ main.dart updated" -ForegroundColor Green

Write-Host "Running flutter clean..." -ForegroundColor Cyan
flutter clean

Write-Host "Running flutter pub get --offline..." -ForegroundColor Cyan
flutter pub get --offline

Write-Host "Connected devices:" -ForegroundColor Cyan
flutter devices

Write-Host "Running app..." -ForegroundColor Cyan
flutter run --no-pub

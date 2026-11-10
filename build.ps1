# build.ps1 - Maths Heist WebAssembly Build and Asset Sync Script

Write-Host "Starting Pygbag build process..." -ForegroundColor Cyan
# 1. Compile the Python game to WebAssembly (.apk)
python -X utf8 -m pygbag --build .

Write-Host "`nSyncing external assets for Scoreboard and HTML overlays..." -ForegroundColor Cyan
# 2. Ensure the build directory exists
$targetDir = "build\web"
if (-not (Test-Path -Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}

# 3. Copy standalone root files (Scoreboard, Config, Fonts, Icons)
$rootFiles = @(
    "scoreboard.html", 
    "classes.json", 
    "favicon.png", 
    "Inter-Regular.ttf"
)

foreach ($file in $rootFiles) {
    if (Test-Path $file) {
        Copy-Item -Path $file -Destination "$targetDir\" -Force
        Write-Host " [+] Copied $file" -ForegroundColor Green
    } else {
        Write-Host " [!] Warning: $file not found in root directory." -ForegroundColor Yellow
    }
}

# 4. Copy asset and data directories recursively
$directories = @("img", "data")

foreach ($dir in $directories) {
    if (Test-Path $dir) {
        # Copy-Item with -Recurse to a new folder name can nest awkwardly in PowerShell, 
        # so we ensure the destination subfolder exists and copy contents.
        $destPath = "$targetDir\$dir"
        if (-not (Test-Path -Path $destPath)) {
            New-Item -ItemType Directory -Path $destPath | Out-Null
        }
        Copy-Item -Path "$dir\*" -Destination $destPath -Recurse -Force
        Write-Host " [+] Copied $dir\ and its contents" -ForegroundColor Green
    } else {
        Write-Host " [!] Warning: $dir\ directory not found." -ForegroundColor Yellow
    }
}

Write-Host "`nBuild complete! Assets are synced to build\web\." -ForegroundColor Cyan
Write-Host "Run your local server to test:" -ForegroundColor DarkGray
Write-Host "python -m http.server 8080 --directory build/web" -ForegroundColor White
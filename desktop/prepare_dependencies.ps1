$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ChromaprintVersion = "1.6.1"
$ArchiveName = "chromaprint-fpcalc-$ChromaprintVersion-windows-x86_64.zip"
$DownloadUrl = "https://github.com/acoustid/chromaprint/releases/download/v$ChromaprintVersion/$ArchiveName"
$ExpectedSha256 = "735d6182b38e9f364b84ce6f4ccd682c75e2851de89735711d6b762d12b92a4e"
$LicenseUrl = "https://raw.githubusercontent.com/acoustid/chromaprint/v$ChromaprintVersion/LICENSE.md"
$LgplUrl = "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt"
$Destination = Join-Path $PSScriptRoot "vendor\fpcalc"
$Fpcalc = Join-Path $Destination "fpcalc.exe"
$License = Join-Path $Destination "LICENSE.md"
$LgplLicense = Join-Path $Destination "COPYING.LGPL-2.1.txt"

New-Item -ItemType Directory -Path $Destination -Force | Out-Null

if (-not (Test-Path -LiteralPath $Fpcalc)) {
    $Temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("kaos-tunes-fpcalc-" + [Guid]::NewGuid())
    $Archive = Join-Path $Temporary $ArchiveName
    $Extracted = Join-Path $Temporary "extracted"
    New-Item -ItemType Directory -Path $Temporary -Force | Out-Null
    try {
        Write-Host "Downloading Chromaprint fpcalc $ChromaprintVersion..."
        Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $Archive
        $ActualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
        if ($ActualSha256 -ne $ExpectedSha256) {
            throw "Chromaprint archive checksum mismatch. Expected $ExpectedSha256, received $ActualSha256."
        }
        Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force
        $DownloadedFpcalc = Get-ChildItem -LiteralPath $Extracted -Filter "fpcalc.exe" -Recurse | Select-Object -First 1
        if ($null -eq $DownloadedFpcalc) {
            throw "The verified Chromaprint archive did not contain fpcalc.exe."
        }
        Copy-Item -LiteralPath $DownloadedFpcalc.FullName -Destination $Fpcalc -Force
    }
    finally {
        if (Test-Path -LiteralPath $Temporary) {
            Remove-Item -LiteralPath $Temporary -Recurse -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $License)) {
    Invoke-WebRequest -UseBasicParsing -Uri $LicenseUrl -OutFile $License
}
if (-not (Test-Path -LiteralPath $LgplLicense)) {
    Invoke-WebRequest -UseBasicParsing -Uri $LgplUrl -OutFile $LgplLicense
}

& $Fpcalc -version | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "The bundled fpcalc executable failed its version check."
}

Write-Host "Redistributable metadata dependency is ready: $Fpcalc"

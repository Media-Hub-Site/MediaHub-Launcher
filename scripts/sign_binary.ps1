<#
.SYNOPSIS
    Firma digital de binarios e instaladores para Media Hub.
    Soporta certificados comerciales PFX (vía variable/secreto) o generación automática
    de certificado de firma de código con timestamping RFC 3161 (DigiCert / Sectigo).

.PARAMETER FilePath
    Ruta del ejecutable o instalador a firmar.
.PARAMETER PfxPath
    (Opcional) Ruta de certificado PFX existente.
.PARAMETER PfxPassword
    (Opcional) Contraseña del PFX.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,

    [Parameter(Mandatory=$false)]
    [string]$PfxPath = "",

    [Parameter(Mandatory=$false)]
    [string]$PfxPassword = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $FilePath)) {
    Write-Error "El archivo especificado no existe: $FilePath"
    exit 1
}

Write-Host "Iniciando proceso de firma digital para: $FilePath" -ForegroundColor Cyan

$cert = $null

# 1. Si se proporciona PFX por ruta o variable de entorno
if ($PfxPath -and (Test-Path $PfxPath)) {
    Write-Host "Cargando certificado desde $PfxPath..." -ForegroundColor Yellow
    $securePass = if ($PfxPassword) { ConvertTo-SecureString $PfxPassword -AsPlainText -Force } else { $null }
    $cert = Get-PfxCertificate -FilePath $PfxPath
} elseif ($env:MEDIAHUB_CERT_BASE64) {
    Write-Host "Cargando certificado desde variable de entorno MEDIAHUB_CERT_BASE64..." -ForegroundColor Yellow
    $certBytes = [Convert]::FromBase64String($env:MEDIAHUB_CERT_BASE64)
    $tempPfx = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "mediahub_cert.pfx")
    [System.IO.File]::WriteAllBytes($tempPfx, $certBytes)
    $pass = if ($env:MEDIAHUB_CERT_PASSWORD) { $env:MEDIAHUB_CERT_PASSWORD } else { "" }
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($tempPfx, $pass)
} else {
    # 2. Buscar certificado existente en el almacén de certificados del usuario o crear uno
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*Media Hub*" -or $_.Subject -like "*Alan Dave*" } | Select-Object -First 1

    if (-not $cert) {
        Write-Host "Generando certificado de firma de código (Code Signing)..." -ForegroundColor Yellow
        $cert = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject "CN=Media Hub (Alan Dave), O=Media-Hub-Site, C=CL" `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -KeyUsage DigitalSignature `
            -KeySpec Signature `
            -KeyLength 2048 `
            -HashAlgorithm "SHA256" `
            -NotAfter (Get-Date).AddYears(5)
        Write-Host "Certificado creado con huella digital: $($cert.Thumbprint)" -ForegroundColor Green
    } else {
        Write-Host "Usando certificado local: $($cert.Subject) [Thumbprint: $($cert.Thumbprint)]" -ForegroundColor Green
    }
}

# 3. Firmar el archivo usando Set-AuthenticodeSignature con servidor de marcas de tiempo RFC 3161
# El timestamp garantiza que la firma siga siendo válida incluso si el certificado caduca en el futuro.
$timestampServers = @(
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com",
    "http://timestamp.globalsign.com/tsa/r6advanced1"
)

$signed = $false
foreach ($ts in $timestampServers) {
    try {
        Write-Host "Firmando con marca de tiempo de: $ts ..."
        $sig = Set-AuthenticodeSignature -FilePath $FilePath -Certificate $cert -TimestampServer $ts -HashAlgorithm "SHA256"
        if ($sig.Status -eq "Valid" -or $sig.Status -eq "UnknownError") {
            # UnknownError a veces aparece en certificados autofirmados que aún no están en la raíz de confianza, pero la firma está insertada correctamente.
            Write-Host "Archivo firmado exitosamente. Estado de firma: $($sig.StatusMessage) ($($sig.Status))" -ForegroundColor Green
            $signed = $true
            break
        } else {
            Write-Warning "Firma realizada con estado: $($sig.StatusMessage)"
            $signed = $true
            break
        }
    } catch {
        Write-Warning "Fallo con $ts : $_. Reintentando con siguiente servidor..."
    }
}

if (-not $signed) {
    # Firma sin timestamp como último recurso
    Write-Host "Firmando sin servidor de marcas de tiempo..." -ForegroundColor Yellow
    $sig = Set-AuthenticodeSignature -FilePath $FilePath -Certificate $cert -HashAlgorithm "SHA256"
    Write-Host "Resultado final: $($sig.StatusMessage) ($($sig.Status))" -ForegroundColor Green
}

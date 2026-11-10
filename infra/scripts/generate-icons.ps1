param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\..\apps\desktop\src-tauri\icons")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function New-IconPng {
    param([int]$Size, [string]$Path)

    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::FromArgb(11, 18, 32))

    $margin = [math]::Round($Size * 0.12)
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Point(0, 0)),
        (New-Object System.Drawing.Point($Size, $Size)),
        [System.Drawing.Color]::FromArgb(79, 140, 255),
        [System.Drawing.Color]::FromArgb(62, 207, 142)
    )
    $graphics.FillEllipse($brush, $margin, $margin, $Size - (2 * $margin), $Size - (2 * $margin))

    $fontSize = [math]::Max(8, [math]::Round($Size * 0.38))
    $font = New-Object System.Drawing.Font(
        "Segoe UI",
        $fontSize,
        [System.Drawing.FontStyle]::Bold,
        [System.Drawing.GraphicsUnit]::Pixel
    )
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $rect = New-Object System.Drawing.RectangleF(0, 0, $Size, $Size)
    $graphics.DrawString("SF", $font, [System.Drawing.Brushes]::White, $rect, $format)

    $graphics.Dispose()
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    $font.Dispose()
    $format.Dispose()
    $brush.Dispose()
}

New-IconPng -Size 32 -Path (Join-Path $OutputDir "32x32.png")
New-IconPng -Size 128 -Path (Join-Path $OutputDir "128x128.png")
New-IconPng -Size 256 -Path (Join-Path $OutputDir "128x128@2x.png")

$pngPath = Join-Path $OutputDir "128x128@2x.png"
$png = [System.IO.File]::ReadAllBytes($pngPath)
$icoPath = Join-Path $OutputDir "icon.ico"

$stream = New-Object System.IO.MemoryStream
$writer = New-Object System.IO.BinaryWriter($stream)
$writer.Write([UInt16]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]1)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([Byte]0)
$writer.Write([UInt16]1)
$writer.Write([UInt16]32)
$writer.Write([UInt32]$png.Length)
$writer.Write([UInt32]22)
$writer.Write($png)
$writer.Flush()

[System.IO.File]::WriteAllBytes($icoPath, $stream.ToArray())
$writer.Dispose()
$stream.Dispose()

Write-Output "Icônes générées dans $OutputDir"

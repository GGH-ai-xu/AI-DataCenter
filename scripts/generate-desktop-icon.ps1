param(
  [string]$OutputDir = "desktop-shell/build"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function New-RoundedRectPath([float]$x, [float]$y, [float]$width, [float]$height, [float]$radius) {
  $path = New-Object System.Drawing.Drawing2D.GraphicsPath
  $diameter = $radius * 2
  $path.AddArc($x, $y, $diameter, $diameter, 180, 90)
  $path.AddArc($x + $width - $diameter, $y, $diameter, $diameter, 270, 90)
  $path.AddArc($x + $width - $diameter, $y + $height - $diameter, $diameter, $diameter, 0, 90)
  $path.AddArc($x, $y + $height - $diameter, $diameter, $diameter, 90, 90)
  $path.CloseFigure()
  return $path
}

$targetDir = Join-Path $PSScriptRoot "..\\$OutputDir"
$targetDir = [System.IO.Path]::GetFullPath($targetDir)
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$size = 256
$bitmap = New-Object System.Drawing.Bitmap $size, $size
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$graphics.Clear([System.Drawing.Color]::Transparent)

$paper = [System.Drawing.Color]::FromArgb(248, 245, 240)
$paperSoft = [System.Drawing.Color]::FromArgb(255, 255, 240)
$ink = [System.Drawing.Color]::FromArgb(26, 26, 26)
$inkSoft = [System.Drawing.Color]::FromArgb(102, 102, 102)
$gold = [System.Drawing.Color]::FromArgb(212, 175, 55)

$backgroundPath = New-RoundedRectPath 12 12 232 232 48
$backgroundBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush ([System.Drawing.RectangleF]::new(12, 12, 232, 232)), $paperSoft, $paper, 45
$graphics.FillPath($backgroundBrush, $backgroundPath)

$borderPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(28, $ink), 4)
$graphics.DrawPath($borderPen, $backgroundPath)

$washBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(20, $ink))
$graphics.FillEllipse($washBrush, 22, 36, 140, 88)
$graphics.FillEllipse($washBrush, 126, 132, 112, 70)

$ringPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(220, $inkSoft), 18)
$ringPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$ringPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$graphics.DrawArc($ringPen, 48, 42, 144, 144, 208, 258)

$accentPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(168, $gold), 8)
$accentPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$accentPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$graphics.DrawArc($accentPen, 70, 64, 124, 124, 312, 72)

$fontFamily = "Microsoft YaHei UI"
$titleFont = New-Object System.Drawing.Font($fontFamily, 96, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$sealFont = New-Object System.Drawing.Font($fontFamily, 36, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$titleGlyph = [char]0x6CBB
$sealGlyph = [char]0x53F0

$stringFormat = New-Object System.Drawing.StringFormat
$stringFormat.Alignment = [System.Drawing.StringAlignment]::Center
$stringFormat.LineAlignment = [System.Drawing.StringAlignment]::Center

$textRect = [System.Drawing.RectangleF]::new(48, 54, 132, 132)
$textBrush = New-Object System.Drawing.SolidBrush $ink
$graphics.DrawString($titleGlyph, $titleFont, $textBrush, $textRect, $stringFormat)

$sealPath = New-RoundedRectPath 170 168 56 56 14
$sealStart = [System.Drawing.Color]::FromArgb(214, 42, 70)
$sealEnd = [System.Drawing.Color]::FromArgb(168, 20, 44)
$sealBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush ([System.Drawing.RectangleF]::new(170, 168, 56, 56)), $sealStart, $sealEnd, 45
$graphics.FillPath($sealBrush, $sealPath)

$sealBorder = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(45, 255, 248, 243), 2)
$graphics.DrawPath($sealBorder, $sealPath)

$sealTextBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 248, 243))
$sealRect = [System.Drawing.RectangleF]::new(170, 168, 56, 56)
$graphics.DrawString($sealGlyph, $sealFont, $sealTextBrush, $sealRect, $stringFormat)

$pngPath = Join-Path $targetDir "icon.png"
$icoPath = Join-Path $targetDir "icon.ico"

$bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)

$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$fileStream = [System.IO.File]::Open($icoPath, [System.IO.FileMode]::Create)
$icon.Save($fileStream)
$fileStream.Close()

$icon.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
$backgroundBrush.Dispose()
$borderPen.Dispose()
$washBrush.Dispose()
$ringPen.Dispose()
$accentPen.Dispose()
$titleFont.Dispose()
$sealFont.Dispose()
$stringFormat.Dispose()
$textBrush.Dispose()
$sealBrush.Dispose()
$sealBorder.Dispose()
$sealTextBrush.Dispose()
$backgroundPath.Dispose()
$sealPath.Dispose()

$legacyTestIcon = Join-Path $targetDir "test-icon.ico"
if (Test-Path $legacyTestIcon) {
  Remove-Item $legacyTestIcon -Force
}

Get-ChildItem -Path $targetDir -Filter "icon.*" | Select-Object Name, Length, FullName

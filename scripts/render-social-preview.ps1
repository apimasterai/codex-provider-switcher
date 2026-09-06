param([string]$OutputPath = (Join-Path $PSScriptRoot '../docs/social-preview.png'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::new(1280, 640)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#f6f8fa'))
$ink = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#17201e'))
$muted = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#485751'))
$accent = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#147d64'))
$white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$label = [System.Drawing.Font]::new('Segoe UI', 22, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$heading = [System.Drawing.Font]::new('Segoe UI', 66, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$body = [System.Drawing.Font]::new('Segoe UI', 30, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
$code = [System.Drawing.Font]::new('Consolas', 32, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
try {
    $graphics.FillRectangle($accent, 0, 0, 1280, 12)
    $graphics.DrawString('OPEN SOURCE / INDEPENDENT COMMUNITY TOOL', $label, $accent, 80, 72)
    $graphics.DrawString('Codex Provider Switcher', $heading, $ink, 75, 157)
    $graphics.DrawString('Keep local Desktop history visible across provider switches.', $body, $muted, 80, 270)
    $graphics.DrawString('Windows  /  macOS  /  Linux', $label, $muted, 80, 332)
    $graphics.FillRectangle($ink, 80, 412, 1120, 84)
    $graphics.DrawString('cps use <profile>', $code, $white, 108, 435)
    $graphics.DrawString('github.com/RomaCredit/codex-provider-switcher', $label, $muted, 80, 548)
    $directory = Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputPath))
    $null = New-Item -ItemType Directory -Path $directory -Force
    $bitmap.Save([System.IO.Path]::GetFullPath($OutputPath), [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    foreach ($resource in @($label, $heading, $body, $code, $ink, $muted, $accent, $white, $graphics, $bitmap)) { $resource.Dispose() }
}
Write-Output "Generated $OutputPath"

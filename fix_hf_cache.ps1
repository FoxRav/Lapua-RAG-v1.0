# Korjaa HuggingFace Hub cache-ongelma Windowsissa
# Poistaa rikkinäiset symlinkit ja antaa HuggingFace Hub:n ladata mallit uudelleen

Write-Host "Poistetaan rikkinäinen HuggingFace cache..." -ForegroundColor Yellow

$cachePath = "$env:USERPROFILE\.cache\huggingface\hub\models--docling-project--docling-layout-heron"

if (Test-Path $cachePath) {
    Remove-Item -Recurse -Force $cachePath -ErrorAction SilentlyContinue
    Write-Host "Cache poistettu: $cachePath" -ForegroundColor Green
} else {
    Write-Host "Cache-kansiota ei löytynyt: $cachePath" -ForegroundColor Yellow
}

Write-Host "`nAsetetaan ympäristömuuttujat..." -ForegroundColor Yellow
$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Ympäristömuuttujat asetettu." -ForegroundColor Green
Write-Host "`nVoit nyt ajaa: python process_pdf_for_rag.py" -ForegroundColor Cyan


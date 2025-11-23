# PowerShell-skripti PDF-prosessoinnille RAG:ia varten
# Tämä korjaa Windows-symlink-ongelman

param(
    [string]$Script = "process_all_documents_for_rag.py"
)

Write-Host "Korjataan HuggingFace cache-ongelma..." -ForegroundColor Yellow

# Poista rikkinäinen cache jos se on olemassa
$cachePath = "$env:USERPROFILE\.cache\huggingface\hub\models--docling-project--docling-layout-heron"
if (Test-Path $cachePath) {
    Write-Host "Poistetaan rikkinäinen cache: $cachePath" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $cachePath -ErrorAction SilentlyContinue
}

# Aseta ympäristömuuttuja estämään symlinkkien käyttö
$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Ympäristömuuttujat asetettu. Ajetaan PDF-prosessointi..." -ForegroundColor Green
Write-Host "Käytetään skriptiä: $Script"
Write-Host ""

# Aja Python-skripti
python $Script


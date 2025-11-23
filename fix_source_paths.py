"""
Korjaa source_file-polut JSONL-tiedostoissa normalisoimalla ne suhteellisiksi.

Tämä skripti:
1. Lukee normalized_chunks.jsonl ja tables_normalized.jsonl
2. Normalisoi source_file-polut (poistaa absoluuttiset Windows-polut)
3. Kirjoittaa korjatut tiedostot takaisin
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
_log = logging.getLogger(__name__)


def normalize_source_path(source_file: str) -> str:
    """
    Normalisoi source_file-poluksi suhteellinen polku.
    
    Esim:
    - "F:\\Projekti-Lapua\\...\\Hyvinvointilautakunta\\2024\\..." 
      -> "Hyvinvointilautakunta\\2024\\..."
    - "Hyvinvointilautakunta\\2024\\..." -> "Hyvinvointilautakunta\\2024\\..."
    """
    if not source_file:
        return source_file
    
    # Jos polku on jo suhteellinen (ei ala F:\ tai C:\), palauta sellaisenaan
    if not (source_file.startswith("F:\\") or source_file.startswith("C:\\") or 
            source_file.startswith("F:/") or source_file.startswith("C:/")):
        return source_file
    
    # Etsi viimeinen "DATA_päättävät_elimet" tai vastaava osa
    # ja ota kaikki sen jälkeen
    parts = source_file.replace("\\", "/").split("/")
    
    # Etsi indeksi jossa on organisaatio-kansio (esim. "Hyvinvointilautakunta", "Kaupunginhallitus")
    org_names = [
        "Hyvinvointilautakunta", "Kaupunginhallitus", "Kaupunginvaltuusto",
        "Teknisen lautakunta", "Koululautakunta", "Ympäristölautakunta"
    ]
    
    for i, part in enumerate(parts):
        if part in org_names:
            # Ota kaikki tästä eteenpäin
            normalized = "/".join(parts[i:])
            # Muuta takaisin Windows-poluksi (backslash)
            return normalized.replace("/", "\\")
    
    # Jos ei löydy, yritä ottaa viimeinen osa (tiedostonimi)
    if parts:
        return parts[-1]
    
    return source_file


def fix_jsonl_file(input_path: Path, output_path: Path) -> int:
    """Korjaa JSONL-tiedoston source_file-polut."""
    fixed_count = 0
    
    with open(input_path, "r", encoding="utf-8") as f_in, \
         open(output_path, "w", encoding="utf-8") as f_out:
        
        for line_num, line in enumerate(f_in, 1):
            if not line.strip():
                continue
            
            try:
                chunk = json.loads(line)
                
                # Normalisoi source_file
                if "source_file" in chunk:
                    old_path = chunk["source_file"]
                    new_path = normalize_source_path(old_path)
                    
                    if old_path != new_path:
                        chunk["source_file"] = new_path
                        fixed_count += 1
                        if fixed_count <= 5:  # Näytä ensimmäiset 5 esimerkkiä
                            _log.info(f"Rivi {line_num}: {old_path[:80]}... -> {new_path[:80]}...")
                
                # Kirjoita korjattu rivi
                f_out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                
            except json.JSONDecodeError as e:
                _log.error(f"JSON-virhe rivillä {line_num}: {e}")
                continue
    
    return fixed_count


def main():
    """Pääfunktio."""
    base_dir = Path("106PDF_output")
    
    files_to_fix = [
        ("normalized_chunks.jsonl", "normalized_chunks.jsonl"),
        ("tables_normalized.jsonl", "tables_normalized.jsonl"),
    ]
    
    for input_name, output_name in files_to_fix:
        input_path = base_dir / input_name
        output_path = base_dir / f"{output_name}.fixed"
        
        if not input_path.exists():
            _log.warning(f"Tiedostoa ei löydy: {input_path}")
            continue
        
        _log.info(f"\nKorjataan: {input_name}")
        fixed_count = fix_jsonl_file(input_path, output_path)
        
        if fixed_count > 0:
            # Vaihda tiedostot
            backup_path = base_dir / f"{input_name}.backup"
            input_path.rename(backup_path)
            output_path.rename(input_path)
            _log.info(f"✅ Korjattu {fixed_count} polkua. Backup: {backup_path}")
        else:
            # Poista turha .fixed-tiedosto
            output_path.unlink()
            _log.info(f"✅ Ei korjauksia tarvittu: {input_name}")


if __name__ == "__main__":
    main()


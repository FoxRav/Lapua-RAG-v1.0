# Chunkkien koko-optimointi Lapua-RAG:lle

## Optimaaliset asetukset

### Token-rajat
- **Target**: ~384 tokenia per chunk
- **Max**: 512 tokenia (ehdoton yläraja)
- **Min**: 150 tokenia (poikkeukset: lyhyet päätökset)
- **Overlap**: Ei suoraa tukea HybridChunkerissa, mutta rakenteen mukaan erottelu varmistaa että pykälät eivät katkea

### Miksi nämä arvot?

#### 384 tokenia (target)
- RAG-haku: 6-8 chunkkia × 384 ≈ 2300 tokenia
- Sopii hyvin 8k-16k context-malleille
- Riittävästi kontekstia päätösten ja perustelujen ymmärtämiseen
- Ei liikaa "mössöä" yhteen chunkkiin

#### 512 tokenia (max)
- Ehdoton yläraja
- Liian isot chunkit (>800-1000 tokenia) heikentävät embeddingien tarkkuutta
- Useita eri aiheita samassa vektorissa → huonompi haku

#### 150 tokenia (min)
- Liian pienet chunkit (<100-150 tokenia) eivät kanna riittävää kontekstia
- Poikkeus: lyhyet päätökset säilytetään (esim. "Päätetään: § 81")

## Rakenteen mukaan erottelu

HybridChunker erottelee automaattisesti rakenteen mukaan:
- Yksi päätös + lyhyt perustelu
- Yksi pykälä tai sen selkeä alaluku
- Yksi kokonaisuus (esim. "Muutoksenhakuohje")

Token-raja on "turvaverkko"; ensisijainen logiikka on rakenteessa.

## RAG-haku-optimointi

### Top-k chunkit
- **6-8 chunkkia** on optimaalinen määrä
- 6 × 384 ≈ 2300 tokenia → hyvä 8k-16k context-malleille
- Riittävästi taustaa vastausta varten ilman että prompt paisuu turhaan

### Esimerkki-haku
```
"Etsi kaikki § 81 päätökset 2025 kaupunginhallituksesta"
→ Filtteröi metadatan perusteella
→ Hae top-6 chunkkia
→ ~2300 tokenia kontekstia
```

## Toteutus

### Prosessointi
1. **Docling-prosessointi**: `max_tokens=512`
   - HybridChunker erottelee rakenteen mukaan
   - Token-raja on turvaverkko

2. **Postprosessointi**: Filtteröinti
   - Poistaa liian lyhyet chunkit (<150 tokenia)
   - Säilyttää lyhyet päätökset
   - Varoittaa liian pitkistä chunkkeista

### Tokenien arviointi
- Nopea arvio: ~4 merkkiä per token
- Tarkempi arvio vaatisi tokenizerin käyttöä (hitaampi)

## Tarkistuslista

- ✅ Target: ~384 tokenia
- ✅ Max: 512 tokenia
- ✅ Min: 150 tokenia (poikkeukset)
- ✅ Rakenteen mukaan erottelu (HybridChunker)
- ✅ Liian lyhyet chunkit filtteröity
- ✅ RAG-haku optimoitu (6-8 chunkkia)

## Suorituskyky

### Odotettu tulos
- **Chunkkeja**: ~8000-12000 (vs. 15263 aiemmin)
- **Keskimääräinen koko**: ~384 tokenia
- **Koko-vaihteluväli**: 150-512 tokenia
- **Hakulaatu**: Parempi (vähemmän kohinaa, parempi konteksti)


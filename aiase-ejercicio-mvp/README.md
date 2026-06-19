# Local AI Usage Cost Dashboard (MVP)

Dashboard **local y de solo lectura** que analiza transcripts de **Claude Code**
desde `~/.claude`, estima costos **solo cuando hay datos completos** (modelo +
tokens + precio configurado) y muestra el gasto por día, por modelo y por sesión.

> ⚠️ **Estos costos son estimaciones con tarifas API públicas configuradas
> localmente; no representan facturación real.**

## Garantías de diseño

- **Read-only sobre rutas fuente.** Nunca escribe en `.claude`, `.codex`, Skills,
  transcripts ni configuración. La única ruta de escritura es la carpeta de salida
  (`/tmp/ai-usage-dashboard` por defecto). Toda escritura pasa por
  `Config.assert_write_allowed()`.
- **Offline.** El análisis corre con la red deshabilitada (`socket`/`getaddrinfo`
  bloqueados). La tabla de precios es 100% local y versionada; no se actualiza por red.
- **Sin costos falsos.** Una sesión sin tokens, sin modelo o sin precio nunca
  muestra un costo: queda marcada como *no calculable* con un estado explícito.
- **Verificación de integridad.** Se captura `mtime`/`sha256` de las rutas fuente
  antes y después del scan. Si algo cambió → **NO-GO técnico**.
- **Logs** solo a stdout/stderr (sin logs persistentes por defecto).

## Instalación

No requiere dependencias externas (solo la stdlib de Python ≥ 3.10).

```bash
pip install -e .            # opcional, instala el comando ai-usage-dashboard
# o simplemente usa PYTHONPATH=src
```

## Uso

```bash
# Escanea ~/.claude y escribe el reporte en /tmp/ai-usage-dashboard/report.json
ai-usage-dashboard scan

# Sirve el dashboard en http://127.0.0.1:8765
ai-usage-dashboard serve

# Rutas y salida personalizadas (la salida debe estar fuera de .claude/.codex)
ai-usage-dashboard scan --read-path ~/.claude --output-dir ~/ai-usage-report
```

Sin instalar:

```bash
PYTHONPATH=src python3 -m ai_usage_dashboard.cli serve
```

### Códigos de salida

- `0` — OK.
- `1` — error de política (p. ej. intento de escritura fuera de la ruta permitida).
- `2` — **NO-GO técnico**: las rutas fuente cambiaron durante el scan.

> Nota: si Claude Code está **activo escribiendo en `~/.claude`** mientras escaneas,
> el chequeo de integridad reportará cambios (NO-GO). Es el comportamiento esperado;
> ejecuta el scan con la sesión inactiva para una verificación limpia.

## Estados de costo

| Estado                 | Significado                                             |
|------------------------|---------------------------------------------------------|
| `calculado`            | modelo + tokens + precio → costo input/output/total     |
| `tokens_faltantes`     | modelo conocido pero el transcript no registró tokens   |
| `precio_no_configurado`| modelo presente pero ausente en la tabla de precios     |
| `modelo_desconocido`   | no se pudo determinar el modelo de la sesión            |

Los agregados por día/modelo **excluyen** las sesiones no calculables y las
reportan por separado.

## Tabla de precios (governance)

`src/ai_usage_dashboard/pricing/pricing_table.json` es local y versionada. Cada
modelo incluye `provider`, `input_price`, `output_price`, `unit`, `source`
(URL/documento) y `consulted_at`. Si la fecha está vencida (> `default_stale_after_days`)
o ausente, se emite una advertencia. No se mezclan tarifas API con facturación
real de planes, suscripciones, descuentos o cache billing. **No hay actualización
automática de precios.**

## P1 — Detección de Codex & Skills

Solo informativo: detecta Codex (`~/.codex`) y Skills instaladas y lista metadata
básica. **No calcula costos** para Codex/Skills en el MVP.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Cubre: fixtures válidos/corruptos/sin tokens/modelo desconocido/precio faltante,
verificación de inmutabilidad de fuentes (mtimes/hashes), modo offline, política
de escritura y el KPI de ≥95% de transcripts procesados.

## Arquitectura

```
src/ai_usage_dashboard/
  config.py       # rutas permitidas + política de escritura (guards)
  offline.py      # guard de red (modo offline)
  verify.py       # snapshot/diff de integridad de fuentes
  pricing.py      # carga de la tabla local + governance
  scanner.py      # lectura/parseo de transcripts (resiliente por archivo)
  cost_engine.py  # cálculo de costos con estados explícitos
  aggregate.py    # gasto por día/modelo (excluye no calculables)
  discovery.py    # P1: detección de Codex & Skills
  report.py       # orquestación del scan (offline-guarded)
  server.py       # servidor localhost (loopback)
  cli.py          # comandos scan / serve
  web/            # UI estática (HTML/CSS/JS)
```

## Non-goals (MVP)

- No representa facturación real ni planes/suscripciones.
- No estima tokens desde texto si el transcript no los trae.
- No escribe en rutas fuente ni usa red durante el análisis.
- No es multiusuario.

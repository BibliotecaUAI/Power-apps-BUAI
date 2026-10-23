# BUAI Contador (Power Apps)

App canvas de Bibliotecas UAI. Cada pantalla tiene versión escritorio/tablet (`Contador`, `Portadamenu`, …) y versión móvil (`ContadorM`, `PortadamenuM`, …); `App.StartScreen` elige según `App.Width > App.Height`.

## Estructura

- `app/BUAI_Contador_Prueba_1.msapp` — archivo original tal como se exportó de Power Apps Studio.
- `src/` — contenido extraído del `.msapp`:
  - `src/Controls/*.json` — definición real de cada pantalla (lo que Studio carga).
  - `src/Src/*.pa.yaml` — vista legible de las mismas pantallas, útil para revisar fórmulas.
  - `src/References/`, `src/Resources/`, `src/Assets/` — fuentes de datos, temas e imágenes.
  - `src/.msapp-manifest.json` — orden y nombres originales de las entradas del zip.
- `tools/` — scripts para extraer y reempaquetar.

## Flujo de trabajo

```sh
# Extraer un .msapp nuevo exportado desde Studio
python3 tools/unpack.py app/BUAI_Contador_Prueba_1.msapp src

# Reempaquetar después de editar src/
python3 tools/pack.py src dist/BUAI_Contador_Prueba_1.msapp
```

Luego en Power Apps Studio: **Archivo → Abrir → Examinar** y cargar el `.msapp` de `dist/`.

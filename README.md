# El Bosque de las Palabras Mágicas

Juego educativo de conciencia fonológica, lectoescritura y comprensión lectora para primaria (grados 1.º y 2.º).

## Jugar

El juego se publica como sitio estático con GitHub Pages. Abre el enlace del repositorio y funciona en navegadores de PC y Android compatibles con pygbag/WebAssembly. Si ya lo habías abierto antes, recarga con `Ctrl + Shift + R` para bajar la versión nueva.

## Niveles

**Zona 1 · Sonidos y sílabas**

1. El Río de las Vocales: vocal inicial de cada dibujo (29 palabras).
2. El Puente Silábico: sílaba que falta en la palabra (27 palabras).
3. El Gran Árbol: ordenar las sílabas de palabras de dos y tres sílabas.

**Zona 2 · Comprensión lectora**

4. Palabra y Dibujo: leer la palabra y tocar su dibujo (62 palabras posibles).
5. La Frase Incompleta: elegir la palabra que completa la frase (17 frases).
6. El Pergamino Mágico: ordenar las palabras de una oración (16 oraciones).
7. Cuentos Cortos: preguntas literales sobre 6 cuentos breves.
8. El Gran Cuento: orden de los hechos, inferencias e idea principal (5 cuentos).
9. Verdad o Mentira: decidir si una frase es verdadera o falsa según el texto (8 textos).

En los niveles 7 a 9 el botón «Escuchar texto» hace que Lina lea el texto completo.

## Estructura

- `index.html`, `favicon.png`, `version.txt`: entrada y archivos públicos del build web.
- `juego_web.apk` y `juego_web.tar.gz`: paquete del juego que carga el navegador (contiene `assets/main.py`). **Se regeneran cada vez que cambia `main.py`.**
- `assets/main.py`: código fuente del juego.
- `build/web/`: copia del build generado.

Las partidas guardadas con tres niveles se conservan: quien ya había completado el sendero 3 encuentra el 4 abierto.

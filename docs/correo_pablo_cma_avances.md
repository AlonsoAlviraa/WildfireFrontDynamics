# Correo a Pablo (CMA) — avances, límites y petición

**Para:** pablo.arroyobretano@geacam.com  
**Copia:** Cma (si aplica, como en el hilo)  
**Asunto:** Avances con los IF del Dropbox — límites y qué me ayudaría a validar  

**Adjunto (informe):** `docs/entrega_cma/Informe_tecnico_dinamica_frente_v1.0.docx`  
Ref. documento: **WFD-INF-2026-07-v1.0**

En el correo, tras el saludo o al final, puedes añadir:

```
Te adjunto un informe técnico breve (v1.0) con método, números de
Tobarra y del resto de IF, y limitaciones. Si el formato no os encaja
operativamente, me lo decís y lo adapto.
```

---

Copia desde la línea siguiente:

```
Hola Pablo,

antes de nada, muchas gracias otra vez por los enlaces y por todo el
tiempo que le estáis dedicando con Silvia y el equipo. Sé que no es
poco trabajo filtrar y subir esto, y de verdad se nota.

Cuando me pasasteis los enlaces dije que con los IF me bastaba; ya
los he procesado y, con resultados en la mano, sí me ayudarían un
par de datos del parte para validar (sin pediros la base de datos ni
volúmenes grandes).

Qué he conseguido hasta ahora

He montado un flujo de trabajo que, a partir de las imágenes
térmicas/IR georreferenciadas:

  1) detecta la zona caliente en cada pasada,
  2) compara pasadas consecutivas,
  3) estima una velocidad de avance del frente (m/min),
  4) genera una capa del frente y un informe sencillo por incendio.

He podido trabajar con varios de los IF del Dropbox. El caso que
mejor me ha salido es Tobarra: tenía una referencia del parte
(aprox. 7 m/min y unas 39 ha) y el valor que saco de la secuencia
térmica cae en el mismo orden de magnitud. Eso me da confianza en
el enfoque. En otros IF también obtengo velocidades, pero con menos
certeza al no disponer aún de ancla de parte.

Problemas / límites que me he encontrado

1) Saltos en el tiempo
   Como me avisaste (una sola cámara, dos periodos…), a veces entre
   dos imágenes hay un hueco grande. Ahí el fuego ha podido cambiar
   mucho y mi estimación se vuelve menos fiable.

2) Respecto al KMZ: resulta muy útil para situar geográficamente la
   pasada y la imagen, pero no constituye el contorno del incendio.
   Por tanto, no puede emplearse como perímetro de referencia para
   validar el modelo. Para cuantificar el error geométrico (p. ej.
   distancia en metros respecto a un croquis o capa oficial), sería
   necesario disponer de un perímetro independiente, aunque sea de
   un único instante y de precisión limitada.

3) Modelo de predicción a 15 / 30 / 60 minutos
   Sigo trabajando también con modelos de aprendizaje (y con datos
   abiertos para tener más volumen), pero no quiero presentar como
   operativo algo que aún no está validado. Con vuestros datos, lo
   más sólido que tengo ahora es la dinámica del frente observada
   (velocidades + capas), no una predicción lista para emergencia.

4) Me falta “ancla” operativa en casi todos los IF
   Solo en Tobarra puedo decir que la velocidad se parece a la del
   parte. En Cardoso, Hellín, La Estrella, etc. también estimo
   avance, pero sin Vp o hectáreas del parte no puedo validar si
   tiene sentido.

Qué me ayudaría (si os es fácil)

A) Una tablita muy simple (aunque sea en el propio correo):

   Incendio | Vp media (m/min) o rango | ha del parte | fecha aprox.

   Con 2 o 3 incendios me bastaría (Cardoso, Hellín, La Estrella…).
   Tobarra ya la tengo más o menos cubierta.

B) Si existiera, un croquis o perímetro de un solo incendio
   (shapefile, GeoJSON, croquis georreferenciado…), aunque sea de
   un instante. Me serviría para medir el error geométrico de forma
   rigurosa. Si no lo tenéis, lo entiendo; lo dejaría como
   limitación del trabajo.

C) Si echáis un vistazo de 5 minutos a un informe de ejemplo que os
   pueda mandar: ¿os dice algo útil o es demasiado “de ingeniería”
   y poco de operaciones?

Preguntas concretas (si tenéis un momento)

1) ¿Disponéis normalmente de Vp media o solo de superficie / parte
   narrativo? (así sé qué puedo pedir sin complicaros)

2) ¿El croquis de perímetro lo hace CMA, INFOCAM, o suele quedar
   solo en el centro operativo y no lo tenéis vosotros?

3) Sobre el Cardoso: ¿sigue en el plan o lo damos por no disponible
   de momento?

Qué os puedo devolver

Cuando tenga un poco de esa info (sobre todo la tablita A), os puedo
mandar un resumen claro:

  · en qué incendios cuadra la velocidad con el parte,
  · en cuáles no me atrevo a afirmar nada,
  · y un par de capturas / capas para que veáis el producto.

Mil gracias otra vez,
Alonso
```
